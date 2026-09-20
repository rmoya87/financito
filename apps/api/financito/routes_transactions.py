from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models_analytics import TransactionRule,TransactionSplit
from .services.transaction_ops import apply_rules_to_unverified,detect_internal_transfers,set_splits
from .services.forecast_accuracy import evaluate as forecast_evaluate
router=APIRouter(prefix="/api/v1")
def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()
class RuleIn(BaseModel):
    matcher_type:str=Field(pattern="^(contains|merchant_exact|regex)$");matcher_value:str=Field(min_length=1,max_length=255);category_id:str;priority:int=100;enabled:bool=True
class SplitIn(BaseModel):
    amount:Decimal=Field(gt=0);category_id:str;note:str|None=None
class SplitsIn(BaseModel):splits:list[SplitIn]=Field(min_length=1,max_length=50)
@router.get("/transaction-rules")
def rules(db:Session=Depends(dbdep)):return [{"id":r.id,"matcher_type":r.matcher_type,"matcher_value":r.matcher_value,"category_id":r.category_id,"priority":r.priority,"enabled":r.enabled} for r in db.scalars(select(TransactionRule).order_by(TransactionRule.priority)).all()]
@router.post("/transaction-rules")
def add_rule(p:RuleIn,db:Session=Depends(dbdep)):r=TransactionRule(**p.model_dump());db.add(r);db.flush();changed=apply_rules_to_unverified(db);db.commit();return {"id":r.id,"reclassified":changed}
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
