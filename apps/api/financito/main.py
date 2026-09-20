from __future__ import annotations

from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .migrations import migrate,MIGRATION_VERSION
from .domain.engines import MortgageEngine, MortgagePrepaymentEngine, OptimizationEngine
from .services.financial_analytics import cash_flow,category_spending
from .models import Account, ActionItem, AuditEvent, Budget, CategorizationAudit, Category, Commitment, Document, ExtractedFact, Transaction
from .schemas import AccountCreate, AccountOut, ActionUpdate, BudgetCreate, CommitmentCreate, DocumentIndexRequest, FactUpdate, ForecastRequest, MortgageScenarioRequest, MortgagePrepaymentRequest, OptimizationRequest, TransactionCategoryUpdate, TransactionOut
from .security import LocalSecurityMiddleware, create_session
from .routes_extended import router as extended_router
from .routes_analytics import router as analytics_router
from .routes_transactions import router as transactions_router
from .routes_domain import router as domain_router
from .routes_config import router as config_router
from .routes_privacy import router as privacy_router
from .routes_observability import router as observability_router
from .services.vault_watcher import VaultWatcher
from .services.categorization import ensure_categories
from .services.documents import index_document,reprocess_document,safe_path
from .services.forecast import forecast
from .services.imports import import_csv
from .services.local_ai import status as ai_status
from .services.secure_config import provider_status
from .services.snapshots import record_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Financito may only bind to loopback")
    migrate()
    with SessionLocal() as db:
        ensure_categories(db); db.commit()
    watcher=VaultWatcher(); watcher.start()
    try:
        yield
    finally:
        watcher.stop()

app = FastAPI(title="Financito Local API", version="0.3.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(LocalSecurityMiddleware)
app.include_router(extended_router)
app.include_router(analytics_router)
app.include_router(transactions_router)
app.include_router(domain_router)
app.include_router(config_router)
app.include_router(privacy_router)
app.include_router(observability_router)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/v1/session")
def session(response: Response):
    return create_session(response)


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count()).select_from(Account)).scalar_one()
    return {"status":"ok","local_only":True,"database":"ok","database_encrypted":not settings.allow_plaintext_sqlite,"schema_version":MIGRATION_VERSION,"vault":str(settings.vault_dir),"vault_exists":settings.vault_dir.exists(),"frontend_built":settings.frontend_dir.exists(),"ai":ai_status(),"providers":provider_status()}


@app.get("/api/v1/categories")
def categories(db: Session = Depends(get_db)):
    return [{"id":c.id,"name":c.name,"system_key":c.system_key} for c in db.scalars(select(Category).order_by(Category.name)).all()]


@app.get("/api/v1/accounts", response_model=list[AccountOut])
def accounts(db: Session = Depends(get_db)):
    return db.scalars(select(Account).order_by(Account.name)).all()


@app.post("/api/v1/accounts", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    row=Account(**payload.model_dump()); db.add(row); db.flush()
    record_snapshot(db,"account",row.id,{"balance":str(row.current_balance),"available_balance":None if row.available_balance is None else str(row.available_balance),"currency":row.currency},source="account_created")
    db.add(AuditEvent(event_type="account_created",entity_type="account",entity_id=row.id))
    db.commit(); db.refresh(row); return row


@app.get("/api/v1/transactions", response_model=list[TransactionOut])
def transactions(account_id:str|None=None,start:date|None=None,end:date|None=None,limit:int=Query(200,ge=1,le=1000),db:Session=Depends(get_db)):
    stmt=select(Transaction).order_by(Transaction.booking_date.desc(),Transaction.created_at.desc()).limit(limit)
    if account_id: stmt=stmt.where(Transaction.account_id==account_id)
    if start: stmt=stmt.where(Transaction.booking_date>=start)
    if end: stmt=stmt.where(Transaction.booking_date<=end)
    return db.scalars(stmt).all()


@app.post("/api/v1/imports/csv")
async def import_transactions(account_id:str,file:UploadFile=File(...),db:Session=Depends(get_db)):
    if not db.get(Account,account_id): raise HTTPException(404,"Account not found")
    content=await file.read()
    if len(content)>20*1024*1024: raise HTTPException(413,"File too large")
    result=import_csv(db,account_id,content,file.filename or "upload.csv")
    db.add(AuditEvent(event_type="transactions_imported",entity_type="account",entity_id=account_id,metadata_json=json.dumps(result.__dict__)))
    db.commit(); return result.__dict__


@app.patch("/api/v1/transactions/{transaction_id}/category", response_model=TransactionOut)
def update_category(transaction_id:str,payload:TransactionCategoryUpdate,db:Session=Depends(get_db)):
    tx=db.get(Transaction,transaction_id)
    if not tx: raise HTTPException(404,"Transaction not found")
    if not db.get(Category,payload.category_id): raise HTTPException(404,"Category not found")
    previous=tx.category_id; tx.category_id=payload.category_id; tx.categorization_method="manual"; tx.categorization_confidence=Decimal("1"); tx.user_verified=True
    db.add(CategorizationAudit(transaction_id=tx.id,previous_category_id=previous,new_category_id=payload.category_id,method="manual",confidence=Decimal("1"),changed_by="user"))
    db.commit(); db.refresh(tx); return tx


@app.get("/api/v1/dashboard")
def dashboard(db:Session=Depends(get_db)):
    today=date.today(); start=today.replace(day=1)
    txs=db.scalars(select(Transaction).where(and_(Transaction.booking_date>=start,Transaction.booking_date<=today))).all()
    flow_data=cash_flow(db,start,today)
    balances=sum((a.current_balance for a in db.scalars(select(Account)).all()),Decimal("0"))
    upcoming=db.scalars(select(Commitment).where(and_(Commitment.due_date>=today,Commitment.due_date<=today+timedelta(days=45),Commitment.status=="active")).order_by(Commitment.due_date)).all()
    actions=db.scalars(select(ActionItem).where(ActionItem.status.in_(["pending","in_progress"])).order_by(ActionItem.due_date.asc().nullslast()).limit(10)).all()
    category_rows=category_spending(db,start,today)
    return {"period":{"start":start,"end":today},"liquidity":str(balances),"income":str(flow_data["income"]),"expenses":str(flow_data["expenses"]),"savings":str(flow_data["savings"]),"savings_rate":str(flow_data["savings_rate"]) if flow_data["savings_rate"] is not None else None,"spending_by_category":[{"category":r["category"],"amount":str(r["amount"])} for r in category_rows],"upcoming_commitments":[{"id":c.id,"title":c.title,"amount":str(c.amount),"due_date":c.due_date} for c in upcoming],"actions":[{"id":a.id,"title":a.title,"priority":a.priority,"due_date":a.due_date,"status":a.status} for a in actions]}


@app.post("/api/v1/budgets")
def create_budget(payload:BudgetCreate,db:Session=Depends(get_db)):
    if not db.get(Category,payload.category_id): raise HTTPException(404,"Category not found")
    row=Budget(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row); return {"id":row.id}


@app.get("/api/v1/budgets")
def list_budgets(db:Session=Depends(get_db)):
    rows=db.scalars(select(Budget)).all()
    return [{"id":r.id,"category_id":r.category_id,"amount":str(r.amount),"period_type":r.period_type,"currency":r.currency} for r in rows]


@app.post("/api/v1/commitments")
def create_commitment(payload:CommitmentCreate,db:Session=Depends(get_db)):
    row=Commitment(**payload.model_dump(),source_type="manual"); db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"title":row.title,"amount":str(row.amount),"due_date":row.due_date}


@app.get("/api/v1/commitments")
def list_commitments(db:Session=Depends(get_db)):
    rows=db.scalars(select(Commitment).order_by(Commitment.due_date)).all()
    return [{"id":r.id,"title":r.title,"amount":str(r.amount),"due_date":r.due_date,"status":r.status,"confidence":str(r.confidence)} for r in rows]


@app.post("/api/v1/forecast")
def calculate_forecast(payload:ForecastRequest,db:Session=Depends(get_db)):
    result=forecast(db,payload.start,payload.end)
    return {k:(str(v) if isinstance(v,Decimal) else v) for k,v in result.__dict__.items()}


@app.post("/api/v1/documents/index")
def index_doc(payload:DocumentIndexRequest,db:Session=Depends(get_db)):
    try: indexed=index_document(db,payload.path,payload.document_type)
    except FileNotFoundError: raise HTTPException(404,"Document not found")
    except ValueError as exc: raise HTTPException(400,str(exc))
    db.add(AuditEvent(event_type="document_indexed",entity_type="document",entity_id=indexed.document.id)); db.commit()
    return {"id":indexed.document.id,"file_name":indexed.document.file_name,"facts_created":indexed.facts_created,"chunks_created":indexed.chunks_created}


@app.get("/api/v1/documents")
def documents(db:Session=Depends(get_db)):
    rows=db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return [{"id":r.id,"file_name":r.file_name,"document_type":r.document_type,"status":r.status,"page_count":r.page_count} for r in rows]


@app.get("/api/v1/documents/{document_id}/facts")
def document_facts(document_id:str,db:Session=Depends(get_db)):
    rows=db.scalars(select(ExtractedFact).where(ExtractedFact.document_id==document_id)).all()
    return [{"id":r.id,"fact_type":r.fact_type,"key":r.key,"value":json.loads(r.value_json),"confidence":str(r.confidence),"status":r.status,"source_page":r.source_page,"source_section":r.source_section,"user_verified":r.user_verified} for r in rows]


@app.post("/api/v1/documents/{document_id}/reprocess")
def reprocess_doc(document_id:str,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    try: indexed=reprocess_document(db,row)
    except (FileNotFoundError,ValueError) as exc: raise HTTPException(400,str(exc))
    db.add(AuditEvent(event_type="document_reprocessed",entity_type="document",entity_id=row.id));db.commit()
    return {"id":row.id,"document_type":row.document_type,"facts_created":indexed.facts_created,"chunks_created":indexed.chunks_created}

@app.get("/api/v1/documents/{document_id}/file")
def document_file(document_id:str,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    try: path=safe_path(Path(row.file_path))
    except (FileNotFoundError,ValueError) as exc: raise HTTPException(404,str(exc))
    return FileResponse(path,media_type=row.mime_type or "application/octet-stream",filename=row.file_name,content_disposition_type="inline")


@app.patch("/api/v1/facts/{fact_id}")
def update_fact(fact_id:str,payload:FactUpdate,db:Session=Depends(get_db)):
    row=db.get(ExtractedFact,fact_id)
    if not row: raise HTTPException(404,"Fact not found")
    row.status=payload.status; row.user_verified=payload.user_verified; db.commit()
    return {"id":row.id,"status":row.status,"user_verified":row.user_verified}


@app.get("/api/v1/actions")
def actions(status:str|None=None,db:Session=Depends(get_db)):
    stmt=select(ActionItem).order_by(ActionItem.due_date.asc().nullslast(),ActionItem.created_at.desc())
    if status: stmt=stmt.where(ActionItem.status==status)
    rows=db.scalars(stmt).all()
    return [{"id":r.id,"title":r.title,"action_type":r.action_type,"priority":r.priority,"status":r.status,"due_date":r.due_date,"notes":r.notes} for r in rows]


@app.patch("/api/v1/actions/{action_id}")
def update_action(action_id:str,payload:ActionUpdate,db:Session=Depends(get_db)):
    row=db.get(ActionItem,action_id)
    if not row: raise HTTPException(404,"Action not found")
    row.status=payload.status; row.notes=payload.notes
    if payload.status=="done": row.completed_at=datetime.now().astimezone()
    db.commit(); return {"id":row.id,"status":row.status}


@app.post("/api/v1/mortgage/scenario")
def mortgage_scenario(payload:MortgageScenarioRequest):
    result=MortgageEngine.amortization(payload.principal,payload.annual_rate,payload.months)
    return {"monthly_payment":str(result.monthly_payment),"total_payments":str(result.total_payments),"total_interest":str(result.total_interest)}


@app.post("/api/v1/mortgage/prepayment")
def mortgage_prepayment(payload:MortgagePrepaymentRequest):
    try:
        result=MortgagePrepaymentEngine.compare(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    return {k:(str(v) if isinstance(v,Decimal) else v) for k,v in result.__dict__.items()}


@app.post("/api/v1/optimization/calculate")
def optimization(payload:OptimizationRequest):
    result=OptimizationEngine.calculate(**payload.model_dump())
    return {"status":result.status,"net_annual_benefit":str(result.net_annual_benefit) if result.net_annual_benefit is not None else None,"break_even_months":str(result.break_even_months) if result.break_even_months is not None else None}


@app.get("/api/v1/audit")
def audit(limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id":r.id,"event_type":r.event_type,"entity_type":r.entity_type,"entity_id":r.entity_id,"created_at":r.created_at} for r in rows]


if settings.frontend_dir.exists():
    assets=settings.frontend_dir/"_next"
    if assets.exists(): app.mount("/_next",StaticFiles(directory=assets),name="next-assets")
    @app.get("/{path:path}",include_in_schema=False)
    def frontend(path:str):
        candidate=settings.frontend_dir/path
        if path and candidate.is_file(): return FileResponse(candidate)
        html=candidate/"index.html" if path else settings.frontend_dir/"index.html"
        if html.exists(): return FileResponse(html)
        fallback=settings.frontend_dir/"404.html"
        if fallback.exists(): return FileResponse(fallback,status_code=404)
        raise HTTPException(404)
