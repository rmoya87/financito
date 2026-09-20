from __future__ import annotations
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models_analytics import TransactionRule,TransactionSplit
from .services.transaction_ops import apply_category_semantics,apply_rules_to_unverified,detect_internal_transfers,detect_refunds,set_splits
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
    matcher_type:str=Field(pattern="^(contains|merchant_exact|regex)$");matcher_value:str=Field(min_length=1,max_length=255);category_id:str;priority:int=100;enabled:bool=True
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
    previous=tx.category_id
    tx.category_id=p.category_id;tx.categorization_method="manual";tx.categorization_confidence=Decimal("1");tx.user_verified=True
    apply_category_semantics(db,tx)
    db.add(CategorizationAudit(transaction_id=tx.id,previous_category_id=previous,new_category_id=p.category_id,method="manual",confidence=Decimal("1"),changed_by="user"))
    learned=propagate_verified_merchant(db,tx) if p.apply_to_existing else 0
    rule_id=None;reclassified=0
    merchant=normalize_text(tx.merchant_raw or "")
    if p.create_rule and merchant:
        rule=db.scalar(select(TransactionRule).where(TransactionRule.matcher_type=="merchant_exact",TransactionRule.matcher_value==merchant))
        if rule is None:
            rule=TransactionRule(matcher_type="merchant_exact",matcher_value=merchant,category_id=p.category_id,priority=50,enabled=True);db.add(rule);db.flush()
        else:
            rule.category_id=p.category_id;rule.enabled=True;rule.priority=min(rule.priority,50)
        rule_id=rule.id
        if p.apply_to_existing:reclassified=apply_rules_to_unverified(db)
    db.commit()
    return {"id":tx.id,"rule_id":rule_id,"learned":learned,"reclassified":reclassified,"merchant_rule_available":bool(merchant)}
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
