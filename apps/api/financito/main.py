from __future__ import annotations

from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
import json
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .migrations import migrate,MIGRATION_VERSION
from .domain.engines import MortgageEngine, MortgagePrepaymentEngine, MortgageRatePathEngine, OptimizationEngine
from .services.financial_analytics import cash_flow,category_spending
from .models import Account, ActionItem, AuditEvent, Budget, CategorizationAudit, Category, Commitment, Contract, Document, ExtractedFact, Mortgage, Transaction
from .models_analytics import EntityLink
from .models_extended import InsurancePolicy
from .schemas import AccountCreate, AccountOut, ActionUpdate, BudgetCreate, CommitmentCreate, DocumentEntityLinkUpdate, DocumentIndexRequest, DocumentMortgageLinkUpdate, FactUpdate, ForecastRequest, ManualFactCreate, MortgageScenarioRequest, MortgagePrepaymentRequest, MortgageRatePathRequest, OptimizationRequest, TransactionCategoryUpdate, TransactionOut
from .security import LocalSecurityMiddleware, create_session
from .routes_extended import router as extended_router
from .routes_analytics import router as analytics_router
from .routes_transactions import router as transactions_router
from .routes_domain import router as domain_router
from .routes_config import router as config_router
from .routes_privacy import router as privacy_router
from .routes_observability import router as observability_router
from .services.vault_watcher import VaultWatcher
from .services.categorization import ensure_categories,propagate_verified_merchant
from .services.transaction_ops import apply_category_semantics,detect_internal_transfers,detect_refunds,pair_internal_transfer_counterpart,set_category_for_same_concept,synchronize_transaction_semantics
from .services.documents import index_document,reprocess_document,safe_path,store_uploaded_document
from .services.evidence import confirm_document_coherent_evidence,confirm_entity_coherent_evidence,link_document_to_entity,review_summary,synchronize_all_document_evidence,synchronize_document_evidence
from .services.document_ai import analyze_document_by_id,domain_insights,latest_analysis
from .services.forecast import forecast
from .services.month_end import month_end_projection
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
        ensure_categories(db)
        synchronize_transaction_semantics(db)
        synchronize_all_document_evidence(db)
        db.commit()
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
def session(request: Request, response: Response):
    return create_session(response, request.cookies.get("financito_session"))


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
def transactions(account_id:str|None=None,start:date|None=None,end:date|None=None,limit:int=Query(200,ge=1,le=5000),db:Session=Depends(get_db)):
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
    transfer_pairs=detect_internal_transfers(db)
    refunds=detect_refunds(db)
    payload={**result.__dict__,"transfer_pairs":transfer_pairs,"refunds":refunds}
    db.add(AuditEvent(event_type="transactions_imported",entity_type="account",entity_id=account_id,metadata_json=json.dumps(payload)))
    db.commit(); return payload


@app.patch("/api/v1/transactions/{transaction_id}/category", response_model=TransactionOut)
def update_category(transaction_id:str,payload:TransactionCategoryUpdate,db:Session=Depends(get_db)):
    tx=db.get(Transaction,transaction_id)
    if not tx: raise HTTPException(404,"Transaction not found")
    if not db.get(Category,payload.category_id): raise HTTPException(404,"Category not found")
    set_category_for_same_concept(db,tx,payload.category_id)
    db.commit(); db.refresh(tx); return tx


@app.get("/api/v1/dashboard")
def dashboard(start:date|None=None,end:date|None=None,db:Session=Depends(get_db)):
    today=date.today(); end=end or today; start=start or end.replace(day=1)
    if end<start: raise HTTPException(400,"La fecha final debe ser igual o posterior a la inicial.")
    flow_data=cash_flow(db,start,end)
    balances=sum((a.current_balance for a in db.scalars(select(Account)).all()),Decimal("0"))
    upcoming=db.scalars(select(Commitment).where(and_(Commitment.due_date>=today,Commitment.due_date<=today+timedelta(days=45),Commitment.status=="active")).order_by(Commitment.due_date)).all()
    actions=db.scalars(select(ActionItem).where(ActionItem.status.in_(["pending","in_progress"])).order_by(ActionItem.due_date.asc().nullslast()).limit(10)).all()
    category_rows=category_spending(db,start,end)
    return {"period":{"start":start,"end":end},"liquidity":str(balances),"income":str(flow_data["income"]),"expenses":str(flow_data["expenses"]),"savings":str(flow_data["savings"]),"savings_rate":str(flow_data["savings_rate"]) if flow_data["savings_rate"] is not None else None,"spending_by_category":[{"category":r["category"],"system_key":r["system_key"],"amount":str(r["amount"])} for r in category_rows],"upcoming_commitments":[{"id":c.id,"title":c.title,"amount":str(c.amount),"due_date":c.due_date} for c in upcoming],"actions":[{"id":a.id,"title":a.title,"action_type":a.action_type,"priority":a.priority,"due_date":a.due_date,"status":a.status,"notes":a.notes,"related_entity_type":a.related_entity_type,"related_entity_id":a.related_entity_id} for a in actions]}


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

@app.get("/api/v1/forecast/month-end")
def calculate_month_end_forecast(as_of:date|None=None,db:Session=Depends(get_db)):
    return month_end_projection(db,as_of)


def _analyze_document_background(document_id:str)->None:
    with SessionLocal() as db:
        try:
            result=analyze_document_by_id(db,document_id)
            db.add(AuditEvent(
                event_type="document_ai_analyzed",
                entity_type="document",
                entity_id=document_id,
                metadata_json=json.dumps({"status":result.get("status")}),
            ))
            db.commit()
        except Exception as exc:
            db.rollback()
            try:
                db.add(AuditEvent(
                    event_type="document_ai_analysis_failed",
                    entity_type="document",
                    entity_id=document_id,
                    metadata_json=json.dumps({"error":str(exc)[:500]}),
                ))
                db.commit()
            except Exception:
                db.rollback()


@app.post("/api/v1/documents/upload")
@app.put("/api/v1/documents/upload",include_in_schema=False)
async def upload_documents(
    background_tasks:BackgroundTasks,
    files:list[UploadFile]=File(...),
    document_type:str=Form("unknown"),
    db:Session=Depends(get_db),
):
    if not files:
        raise HTTPException(400,"No documents supplied")
    uploaded=[]
    for file in files[:20]:
        content=await file.read()
        try:
            stored=store_uploaded_document(file.filename or "documento",content,file.content_type)
            indexed=index_document(db,str(stored),document_type)
            actual=Path(indexed.document.file_path).resolve()
            if actual!=stored.resolve():
                stored.unlink(missing_ok=True)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(400,f"{file.filename or 'documento'}: {exc}")
        except Exception:
            db.rollback()
            raise
        db.add(AuditEvent(
            event_type="document_uploaded",
            entity_type="document",
            entity_id=indexed.document.id,
            metadata_json=json.dumps({"file_name":indexed.document.file_name}),
        ))
        uploaded.append({
            "id":indexed.document.id,
            "file_name":indexed.document.file_name,
            "document_type":indexed.document.document_type,
            "facts_created":indexed.facts_created,
            "chunks_created":indexed.chunks_created,
        })
    db.commit()
    for item in uploaded:
        background_tasks.add_task(_analyze_document_background,item["id"])
    return {"documents":uploaded,"ai_analysis_scheduled":True}


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
    links=db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
    )).all()
    by_document:dict[str,list[dict]]={}
    for link in links:
        by_document.setdefault(link.from_id,[]).append({
            "entity_type":link.to_type,
            "entity_id":link.to_id,
            "confidence":str(link.confidence),
            "source_type":link.source_type,
        })
    return [
        {
            "id":r.id,
            "file_name":r.file_name,
            "document_type":r.document_type,
            "status":r.status,
            "page_count":r.page_count,
            "review":review_summary(db,r.id),
            "ai_analysis":"ready" if latest_analysis(db,r.id) is not None else "not_analyzed",
            "mortgage_id":next((x["entity_id"] for x in by_document.get(r.id,[]) if x["entity_type"]=="mortgage"),None),
            "evidence_links":by_document.get(r.id,[]),
        }
        for r in rows
    ]


@app.get("/api/v1/evidence-groups")
def evidence_groups(db:Session=Depends(get_db)):
    documents={row.id:row for row in db.scalars(select(Document)).all()}
    links=db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
    )).all()
    grouped:dict[tuple[str,str],list[EntityLink]]={}
    for link in links:
        grouped.setdefault((link.to_type,link.to_id),[]).append(link)

    contracts={row.id:row for row in db.scalars(select(Contract)).all()}
    result=[]
    for policy in db.scalars(select(InsurancePolicy)).all():
        contract=contracts.get(policy.contract_id or "")
        docs=grouped.get(("insurance_policy",policy.id),[])
        provider=contract.provider_name if contract else "Aseguradora pendiente"
        label=f"Seguro {policy.insurance_type} · {provider}"
        result.append({
            "entity_type":"insurance_policy","entity_id":policy.id,"kind":"insurance",
            "label":label,"provider":provider,"document_count":len(docs),
            "documents":[{"id":x.from_id,"file_name":documents[x.from_id].file_name} for x in docs if x.from_id in documents],
        })
    for mortgage in db.scalars(select(Mortgage).order_by(Mortgage.lender)).all():
        docs=grouped.get(("mortgage",mortgage.id),[])
        result.append({
            "entity_type":"mortgage","entity_id":mortgage.id,"kind":"mortgage",
            "label":f"Hipoteca · {mortgage.lender}","provider":mortgage.lender,
            "document_count":len(docs),
            "documents":[{"id":x.from_id,"file_name":documents[x.from_id].file_name} for x in docs if x.from_id in documents],
        })
    for contract in contracts.values():
        if contract.contract_type in {"insurance","mortgage"}:
            continue
        docs=grouped.get(("contract",contract.id),[])
        result.append({
            "entity_type":"contract","entity_id":contract.id,"kind":contract.contract_type,
            "label":f"{contract.provider_name} · {contract.contract_type}",
            "provider":contract.provider_name,"document_count":len(docs),
            "documents":[{"id":x.from_id,"file_name":documents[x.from_id].file_name} for x in docs if x.from_id in documents],
        })
    return sorted(result,key=lambda x:(x["kind"],x["label"].lower()))


@app.put("/api/v1/documents/{document_id}/entity-link")
def set_document_entity_link(document_id:str,payload:DocumentEntityLinkUpdate,db:Session=Depends(get_db)):
    document=db.get(Document,document_id)
    if not document: raise HTTPException(404,"Document not found")
    try:
        sync=link_document_to_entity(db,document,payload.entity_type,payload.entity_id)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    db.add(AuditEvent(
        event_type="document_entity_link_updated",
        entity_type="document",
        entity_id=document_id,
        metadata_json=json.dumps({"entity_type":payload.entity_type,"entity_id":payload.entity_id}),
    ))
    db.commit()
    return {"document_id":document_id,"entity_type":payload.entity_type,"entity_id":payload.entity_id,"evidence_sync":sync}


@app.put("/api/v1/documents/{document_id}/mortgage-link")
def set_document_mortgage_link(document_id:str,payload:DocumentMortgageLinkUpdate,db:Session=Depends(get_db)):
    document=db.get(Document,document_id)
    if not document: raise HTTPException(404,"Document not found")
    try:
        sync=link_document_to_entity(db,document,"mortgage",payload.mortgage_id)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    db.commit()
    return {"document_id":document_id,"mortgage_id":payload.mortgage_id,"evidence_sync":sync}


@app.post("/api/v1/documents/{document_id}/confirm-coherent")
def confirm_document_coherent(document_id:str,db:Session=Depends(get_db)):
    if not db.get(Document,document_id): raise HTTPException(404,"Document not found")
    result=confirm_document_coherent_evidence(db,document_id)
    db.commit()
    return result


@app.post("/api/v1/evidence-groups/{entity_type}/{entity_id}/confirm-coherent")
def confirm_group_coherent(entity_type:str,entity_id:str,db:Session=Depends(get_db)):
    try:
        result=confirm_entity_coherent_evidence(db,entity_type,entity_id)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    db.commit()
    return result


@app.get("/api/v1/documents/{document_id}/facts")
def document_facts(document_id:str,db:Session=Depends(get_db)):
    rows=db.scalars(select(ExtractedFact).where(ExtractedFact.document_id==document_id)).all()
    return [{"id":r.id,"fact_type":r.fact_type,"key":r.key,"value":json.loads(r.value_json),"confidence":str(r.confidence),"status":r.status,"source_page":r.source_page,"source_section":r.source_section,"user_verified":r.user_verified} for r in rows]


@app.get("/api/v1/documents/{document_id}/analysis")
def document_analysis(document_id:str,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    analysis=latest_analysis(db,document_id)
    return {
        "document_id":document_id,
        "status":"ready" if analysis is not None else "not_analyzed",
        "analysis":analysis,
        "ai":ai_status(),
    }


@app.post("/api/v1/documents/{document_id}/analyze")
def analyze_document_now(document_id:str,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    try:
        result=analyze_document_by_id(db,document_id)
    except ValueError as exc:
        raise HTTPException(404,str(exc))
    except RuntimeError as exc:
        raise HTTPException(503,str(exc))
    db.add(AuditEvent(
        event_type="document_ai_analyzed",
        entity_type="document",
        entity_id=document_id,
        metadata_json=json.dumps({"status":result.get("status")}),
    ))
    db.commit()
    return result


@app.post("/api/v1/documents/analyze-all")
def analyze_all_documents(background_tasks:BackgroundTasks,db:Session=Depends(get_db)):
    ids=list(db.scalars(select(Document.id).order_by(Document.updated_at.desc())).all())
    for document_id in ids:
        background_tasks.add_task(_analyze_document_background,document_id)
    return {"scheduled":len(ids)}


@app.get("/api/v1/document-insights")
def document_insights(document_type:str|None=None,db:Session=Depends(get_db)):
    return domain_insights(db,document_type)


@app.post("/api/v1/documents/{document_id}/reprocess")
def reprocess_doc(document_id:str,background_tasks:BackgroundTasks,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    try: indexed=reprocess_document(db,row)
    except (FileNotFoundError,ValueError) as exc: raise HTTPException(400,str(exc))
    db.add(AuditEvent(event_type="document_reprocessed",entity_type="document",entity_id=row.id));db.commit()
    background_tasks.add_task(_analyze_document_background,row.id)
    return {"id":row.id,"document_type":row.document_type,"facts_created":indexed.facts_created,"chunks_created":indexed.chunks_created,"ai_analysis_scheduled":True}

@app.get("/api/v1/documents/{document_id}/file")
def document_file(document_id:str,db:Session=Depends(get_db)):
    row=db.get(Document,document_id)
    if not row: raise HTTPException(404,"Document not found")
    try: path=safe_path(Path(row.file_path))
    except (FileNotFoundError,ValueError) as exc: raise HTTPException(404,str(exc))
    return FileResponse(path,media_type=row.mime_type or "application/octet-stream",filename=row.file_name,content_disposition_type="inline")


@app.post("/api/v1/documents/{document_id}/facts")
def create_manual_document_fact(document_id:str,payload:ManualFactCreate,db:Session=Depends(get_db)):
    document=db.get(Document,document_id)
    if not document:raise HTTPException(404,"Document not found")
    value={"value":payload.value,"source":"user_confirmed"}
    if payload.unit:value["unit"]=payload.unit
    if payload.fact_type=="coverage_fact":
        value.update({
            "coverage_type":payload.coverage_type or payload.value,
            "limit_amount":payload.limit_amount,
            "deductible":payload.deductible,
            "conditions":payload.conditions or "",
            "exclusions":payload.exclusions or "",
        })
    row=ExtractedFact(
        document_id=document.id,
        fact_type=payload.fact_type,
        key=payload.key.strip(),
        value_json=json.dumps(value,ensure_ascii=False),
        confidence=Decimal("1"),
        status="confirmed",
        source_page=payload.source_page,
        source_section="Introducido por el usuario",
        user_verified=True,
    )
    db.add(row);db.flush()
    sync=synchronize_document_evidence(db,document)
    db.add(AuditEvent(event_type="document_fact_added_by_user",entity_type="document",entity_id=document.id,metadata_json=json.dumps({"fact_id":row.id,"key":row.key,"fact_type":row.fact_type})))
    db.commit()
    return {"id":row.id,"evidence_sync":sync}

@app.patch("/api/v1/facts/{fact_id}")
def update_fact(fact_id:str,payload:FactUpdate,db:Session=Depends(get_db)):
    row=db.get(ExtractedFact,fact_id)
    if not row: raise HTTPException(404,"Fact not found")
    row.status=payload.status
    row.user_verified=payload.user_verified
    document=db.get(Document,row.document_id)
    sync=None if document is None else synchronize_document_evidence(db,document)
    db.commit()
    return {"id":row.id,"status":row.status,"user_verified":row.user_verified,"evidence_sync":sync}


@app.get("/api/v1/actions")
def actions(status:str|None=None,db:Session=Depends(get_db)):
    stmt=select(ActionItem).order_by(ActionItem.due_date.asc().nullslast(),ActionItem.created_at.desc())
    if status: stmt=stmt.where(ActionItem.status==status)
    rows=db.scalars(stmt).all()
    return [{
        "id":r.id,
        "title":r.title,
        "action_type":r.action_type,
        "priority":r.priority,
        "status":r.status,
        "due_date":r.due_date,
        "notes":r.notes,
        "related_entity_type":r.related_entity_type,
        "related_entity_id":r.related_entity_id,
        "source_type":r.source_type,
        "source_ref":r.source_ref,
    } for r in rows]


@app.patch("/api/v1/actions/{action_id}")
def update_action(action_id:str,payload:ActionUpdate,db:Session=Depends(get_db)):
    row=db.get(ActionItem,action_id)
    if not row: raise HTTPException(404,"Action not found")
    if row.action_type=="review_document_evidence" and payload.status=="done" and row.related_entity_id:
        summary=review_summary(db,row.related_entity_id)
        if summary["pending"]>0:
            raise HTTPException(409,"Revisa o marca como dudosos los datos pendientes antes de completar esta tarea")
    row.status=payload.status
    if payload.notes is not None: row.notes=payload.notes
    if payload.status=="done": row.completed_at=datetime.now().astimezone().replace(tzinfo=None)
    elif payload.status in {"pending","in_progress"}: row.completed_at=None
    db.commit(); return {"id":row.id,"status":row.status}


@app.post("/api/v1/mortgage/scenario")
def mortgage_scenario(payload:MortgageScenarioRequest):
    result=MortgageEngine.amortization(payload.principal,payload.annual_rate,payload.months)
    return {"monthly_payment":str(result.monthly_payment),"total_payments":str(result.total_payments),"total_interest":str(result.total_interest)}


@app.post("/api/v1/mortgage/rate-path")
def mortgage_rate_path(payload:MortgageRatePathRequest):
    try:
        result=MortgageRatePathEngine.simulate(
            payload.principal,
            payload.months,
            payload.initial_annual_rate,
            [(step.month,step.annual_rate) for step in payload.rate_steps],
        )
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    return {
        "total_payments":str(result.total_payments),
        "total_interest":str(result.total_interest),
        "min_monthly_payment":str(result.min_monthly_payment),
        "max_monthly_payment":str(result.max_monthly_payment),
        "final_balance":str(result.final_balance),
        "segments":[{"start_month":s.start_month,"annual_rate":str(s.annual_rate),"monthly_payment":str(s.monthly_payment),"end_balance":str(s.end_balance)} for s in result.segments],
        "notice":"Escenario determinista basado exclusivamente en la senda de tipos introducida; no es una predicción.",
    }


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
    def _frontend_response(path:str,head:bool=False):
        candidate=settings.frontend_dir/path
        if path and candidate.is_file():
            return Response(status_code=200) if head else FileResponse(candidate)
        html=candidate/"index.html" if path else settings.frontend_dir/"index.html"
        if html.exists():
            headers={"Cache-Control":"no-store, max-age=0"}
            return Response(status_code=200,media_type="text/html",headers=headers) if head else FileResponse(html,headers=headers)
        fallback=settings.frontend_dir/"404.html"
        if fallback.exists():
            return Response(status_code=404,media_type="text/html") if head else FileResponse(fallback,status_code=404)
        raise HTTPException(404)

    @app.head("/{path:path}",include_in_schema=False)
    def frontend_head(path:str):
        return _frontend_response(path,head=True)

    @app.get("/{path:path}",include_in_schema=False)
    def frontend(path:str):
        return _frontend_response(path)
