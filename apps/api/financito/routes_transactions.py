from __future__ import annotations
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import String,cast,func,or_,select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models_analytics import TransactionRule,TransactionSplit
from .services.transaction_ops import apply_category_semantics,apply_rules_to_unverified,detect_internal_transfers,detect_refunds,pair_internal_transfer_counterpart,set_category_for_same_concept,set_splits
from .services.forecast_accuracy import evaluate as forecast_evaluate
from .services.financial_analytics import overview as analytics_overview
from .services.ai_categorization import improve_categorization
from .models import CategorizationAudit,Category,Transaction
from .services.categorization import normalize_text,propagate_verified_merchant
router=APIRouter(prefix="/api/v1")
def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()
class RuleIn(BaseModel):
    matcher_type:str=Field(pattern="^(contains|merchant_exact|description_exact|regex)$");matcher_value:str=Field(min_length=1,max_length=255);category_id:str;priority:int=100;enabled:bool=True
class ReviewDecisionIn(BaseModel):
    category_id:str
    create_rule:bool=True
    apply_to_existing:bool=True
class SplitIn(BaseModel):
    amount:Decimal=Field(gt=0);category_id:str;note:str|None=None
class SplitsIn(BaseModel):splits:list[SplitIn]=Field(min_length=1,max_length=50)
class AICategorizeIn(BaseModel):
    limit:int=Field(default=3000,ge=1,le=10000)
    llm_limit:int=Field(default=80,ge=0,le=500)
@router.get("/transaction-rules")
def rules(db:Session=Depends(dbdep)):return [{"id":r.id,"matcher_type":r.matcher_type,"matcher_value":r.matcher_value,"category_id":r.category_id,"priority":r.priority,"enabled":r.enabled} for r in db.scalars(select(TransactionRule).order_by(TransactionRule.priority)).all()]
@router.post("/transaction-rules")
def add_rule(p:RuleIn,db:Session=Depends(dbdep)):
    if not db.get(Category,p.category_id):raise HTTPException(404,"Category not found")
    existing=db.scalar(select(TransactionRule).where(TransactionRule.matcher_type==p.matcher_type,TransactionRule.matcher_value==p.matcher_value))
    if existing:
        for key,value in p.model_dump().items():setattr(existing,key,value)
        row=existing
    else:
        row=TransactionRule(**p.model_dump());db.add(row);db.flush()
    changed=apply_rules_to_unverified(db);db.commit()
    return {"id":row.id,"reclassified":changed,"updated":existing is not None}

@router.patch("/transaction-rules/{rule_id}")
def update_rule(rule_id:str,p:RuleIn,db:Session=Depends(dbdep)):
    row=db.get(TransactionRule,rule_id)
    if not row:raise HTTPException(404,"Rule not found")
    if not db.get(Category,p.category_id):raise HTTPException(404,"Category not found")
    for key,value in p.model_dump().items():setattr(row,key,value)
    changed=apply_rules_to_unverified(db);db.commit()
    return {"id":row.id,"reclassified":changed}

@router.post("/transactions/{transaction_id}/review")
def review_transaction(transaction_id:str,p:ReviewDecisionIn,db:Session=Depends(dbdep)):
    tx=db.get(Transaction,transaction_id)
    if not tx:raise HTTPException(404,"Transaction not found")
    if not db.get(Category,p.category_id):raise HTTPException(404,"Category not found")
    reclassified=set_category_for_same_concept(db,tx,p.category_id) if p.apply_to_existing else 0
    if not p.apply_to_existing:
        previous=tx.category_id
        tx.category_id=p.category_id;tx.categorization_method="manual";tx.categorization_confidence=Decimal("1");tx.user_verified=True
        key=apply_category_semantics(db,tx)
        if key=="internal_transfer":pair_internal_transfer_counterpart(db,tx)
        db.add(CategorizationAudit(transaction_id=tx.id,previous_category_id=previous,new_category_id=p.category_id,method="manual",confidence=Decimal("1"),changed_by="user"))
    concept=normalize_text(tx.description_raw)
    rule=db.scalar(select(TransactionRule).where(TransactionRule.matcher_type=="description_exact",TransactionRule.matcher_value==concept)) if concept else None
    rule_id=None if rule is None else rule.id
    learned=0
    db.commit()
    return {"id":tx.id,"rule_id":rule_id,"learned":learned,"reclassified":reclassified,"concept_rule_available":bool(concept)}
@router.post("/transactions/detect-transfers")
def transfers(db:Session=Depends(dbdep)):n=detect_internal_transfers(db);db.commit();return {"matched_pairs":n}
@router.get("/transactions/{transaction_id}/splits")
def get_splits(transaction_id:str,db:Session=Depends(dbdep)):return [{"id":r.id,"amount":str(r.amount),"category_id":r.category_id,"note":r.note} for r in db.scalars(select(TransactionSplit).where(TransactionSplit.transaction_id==transaction_id)).all()]
@router.put("/transactions/{transaction_id}/splits")
def splits(transaction_id:str,p:SplitsIn,db:Session=Depends(dbdep)):
    try:rows=set_splits(db,transaction_id,[x.model_dump() for x in p.splits])
    except ValueError as e:raise HTTPException(400,str(e))
    db.commit();return {"splits":[{"id":r.id,"amount":str(r.amount),"category_id":r.category_id,"note":r.note} for r in rows]}
@router.get("/forecast/accuracy")
def forecast_accuracy(months:int=6,db:Session=Depends(dbdep)):
    if months<1 or months>24:raise HTTPException(400,"months must be 1..24")
    return forecast_evaluate(db,months)

@router.post("/transactions/detect-refunds")
def refunds(db:Session=Depends(dbdep)):
    n=detect_refunds(db);db.commit();return {"matched_refunds":n}

@router.post("/transactions/ai-categorize")
def ai_categorize(p:AICategorizeIn,db:Session=Depends(dbdep)):
    result=improve_categorization(db,p.limit,p.llm_limit);db.commit();return result

def _transaction_payload(row:Transaction)->dict:
    return {
        "id":row.id,
        "account_id":row.account_id,
        "booking_date":row.booking_date,
        "amount":str(row.amount),
        "currency":row.currency,
        "description_raw":row.description_raw,
        "merchant_raw":row.merchant_raw,
        "category_id":row.category_id,
        "categorization_method":row.categorization_method,
        "categorization_confidence":str(row.categorization_confidence),
        "user_verified":row.user_verified,
        "is_internal_transfer":row.is_internal_transfer,
    }

@router.get("/transactions/page")
def transaction_page(
    q:str|None=None,
    category_id:str|None=None,
    start:date|None=None,
    end:date|None=None,
    page:int=Query(default=1,ge=1),
    page_size:int=Query(default=50,ge=10,le=100),
    db:Session=Depends(dbdep),
):
    if start and end and end<start:
        raise HTTPException(400,"La fecha final debe ser igual o posterior a la inicial.")

    filters=[]
    if category_id:
        filters.append(Transaction.category_id==category_id)
    if start:
        filters.append(Transaction.booking_date>=start)
    if end:
        filters.append(Transaction.booking_date<=end)

    query=(q or "").strip()
    if query:
        needle=f"%{query.lower()}%"
        category_ids=list(db.scalars(
            select(Category.id).where(func.lower(Category.name).like(needle))
        ).all())
        text_filters=[
            func.lower(Transaction.description_raw).like(needle),
            func.lower(func.coalesce(Transaction.merchant_raw,"")).like(needle),
            cast(Transaction.booking_date,String).like(f"%{query}%"),
            cast(Transaction.amount,String).like(f"%{query.replace(',','.')}%"),
        ]
        if category_ids:
            text_filters.append(Transaction.category_id.in_(category_ids))
        filters.append(or_(*text_filters))

    total=int(db.scalar(
        select(func.count()).select_from(Transaction).where(*filters)
    ) or 0)
    pages=max(1,(total+page_size-1)//page_size)
    effective_page=min(page,pages)
    rows=db.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.booking_date.desc(),Transaction.created_at.desc())
        .offset((effective_page-1)*page_size)
        .limit(page_size)
    ).all()
    return {
        "items":[_transaction_payload(row) for row in rows],
        "total":total,
        "page":effective_page,
        "page_size":page_size,
        "pages":pages,
    }

@router.get("/transactions/review-queue")
def review_queue(limit:int=100,db:Session=Depends(dbdep)):
    rows=db.scalars(select(Transaction).where(Transaction.user_verified.is_(False),Transaction.categorization_confidence<Decimal("0.70")).order_by(Transaction.booking_date.desc()).limit(min(max(limit,1),500))).all()
    return [{"id":r.id,"booking_date":r.booking_date,"amount":str(r.amount),"currency":r.currency,"description_raw":r.description_raw,"merchant_raw":r.merchant_raw,"category_id":r.category_id,"confidence":str(r.categorization_confidence),"method":r.categorization_method} for r in rows]

@router.get("/analytics/overview")
def analytics(start:date|None=None,end:date|None=None,db:Session=Depends(dbdep)):
    from datetime import date as _date,timedelta
    end=end or _date.today();start=start or end-timedelta(days=365)
    if end<start:raise HTTPException(400,"end must be >= start")
    return analytics_overview(db,start,end)

@router.delete("/transaction-rules/{rule_id}")
def delete_rule(rule_id:str,db:Session=Depends(dbdep)):
    row=db.get(TransactionRule,rule_id)
    if not row:raise HTTPException(404,"Rule not found")
    db.delete(row);db.commit();return {"deleted":rule_id}
