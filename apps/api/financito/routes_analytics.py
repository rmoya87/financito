from __future__ import annotations
import json
from datetime import date,timedelta
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .domain.analytics import detect_anomalies,detect_recurring,recurring_is_current
from .domain.backtest import amortize_vs_invest,backtest_ma
from .domain.recommendations import score
from .models import Account,ActionItem,Category,Contract,Transaction
from .models_analytics import Anomaly,EntityLink,RecurringPreference,RecurringSeries
from .services.calendar import events
from .services.financial_analytics import ESSENTIAL
from .services.data_quality import reconciliation
from .services.demo import seed
from .services.search_export import export_json,global_search,transactions_csv
router=APIRouter(prefix="/api/v1")
def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()
@router.post("/analytics/refresh")
def refresh(db:Session=Depends(dbdep)):
    recurring=detect_recurring(db);anomalies=detect_anomalies(db);db.commit();return {"recurring_series":len(recurring),"anomalies":len(anomalies)}
def _recurring_row(db:Session,r:RecurringSeries)->dict:
    key=r.merchant_normalized.strip().lower()
    pref=db.scalar(select(RecurringPreference).where(RecurringPreference.merchant_key==key))
    tx=db.scalar(select(Transaction).where(Transaction.merchant_normalized==r.merchant_normalized).order_by(Transaction.booking_date.desc()).limit(1))
    category=db.get(Category,tx.category_id) if tx and tx.category_id else None
    essential=bool(category and category.system_key in ESSENTIAL)
    if pref and pref.essential_override is not None:essential=bool(pref.essential_override)
    contract=db.get(Contract,pref.contract_id) if pref and pref.contract_id else None
    return {
        "id":r.id,"merchant":r.merchant_normalized,"cadence":r.cadence,
        "expected_amount":str(r.expected_amount),"next_expected_date":r.next_expected_date,
        "confidence":str(r.confidence),"action":pref.action if pref else "keep",
        "essential":essential,"essential_override":None if pref is None else pref.essential_override,
        "contract_id":None if pref is None else pref.contract_id,
        "contract_name":None if contract is None else contract.provider_name,
        "spending_class":"fixed_essential" if essential else "fixed_optional",
        "projected":not bool(pref and pref.action=="not_subscription"),
    }


@router.get("/recurring")
def recurring(db:Session=Depends(dbdep)):
    stored=db.scalars(select(RecurringSeries).where(RecurringSeries.status=="active").order_by(RecurringSeries.next_expected_date)).all()
    rows=[];changed=False
    for row in stored:
        if recurring_is_current(row):rows.append(row)
        else:row.status="inactive";changed=True
    if changed:db.flush()
    if not rows:
        expenses=int(db.scalar(select(func.count()).select_from(Transaction).where(Transaction.amount<0,Transaction.is_internal_transfer.is_(False))) or 0)
        if expenses>=3:rows=detect_recurring(db,use_ai=False)
    if changed or (not stored and rows):db.commit()
    return [_recurring_row(db,r) for r in rows if recurring_is_current(r)]


class RecurringPreferenceIn(BaseModel):
    action:str=Field(pattern="^(keep|review|cancel|not_subscription)$")
    essential_override:bool|None=None
    contract_id:str|None=None


@router.patch("/recurring/{series_id}")
def update_recurring(series_id:str,p:RecurringPreferenceIn,db:Session=Depends(dbdep)):
    row=db.get(RecurringSeries,series_id)
    if not row:raise HTTPException(404,"Recurring series not found")
    if p.contract_id and not db.get(Contract,p.contract_id):raise HTTPException(404,"Contract not found")
    key=row.merchant_normalized.strip().lower()
    pref=db.scalar(select(RecurringPreference).where(RecurringPreference.merchant_key==key))
    if pref is None:
        pref=RecurringPreference(merchant_key=key);db.add(pref)
    pref.action=p.action;pref.essential_override=p.essential_override;pref.contract_id=p.contract_id
    existing=db.scalar(select(ActionItem).where(
        ActionItem.source_type=="recurring",ActionItem.source_ref==key,
        ActionItem.status.in_(["pending","in_progress"]),
    ))
    if p.action in {"review","cancel"}:
        title=("Cancelar " if p.action=="cancel" else "Revisar ")+row.merchant_normalized
        if existing is None:
            db.add(ActionItem(
                action_type="recurring_"+p.action,title=title,priority="medium",
                related_entity_type="contract" if p.contract_id else None,
                related_entity_id=p.contract_id,source_type="recurring",source_ref=key,
                notes="Acción elegida desde el patrón recurrente.",
            ))
        else:
            existing.title=title;existing.action_type="recurring_"+p.action
            existing.related_entity_type="contract" if p.contract_id else None;existing.related_entity_id=p.contract_id
    elif existing is not None:
        existing.status="dismissed"
    db.commit();return _recurring_row(db,row)
class AnomalyStatusIn(BaseModel):
    status:str=Field(pattern="^(open|normal|ignored|resolved)$")

@router.get("/anomalies")
def anomalies(start:date|None=None,end:date|None=None,db:Session=Depends(dbdep),account_id:str|None=None,account_type:str|None=None):
    if start and end and end<start:raise HTTPException(400,"La fecha final debe ser igual o posterior a la inicial.")
    allowed_accounts=None
    if account_id:
        allowed_accounts={account_id}
    elif account_type:
        allowed_accounts=set(db.scalars(select(Account.id).where(Account.account_type==account_type)).all())
    out=[]
    for a in db.scalars(select(Anomaly).where(Anomaly.status=="open").order_by(Anomaly.created_at.desc())).all():
        tx=db.get(Transaction,a.transaction_id)
        if tx is None:continue
        if allowed_accounts is not None and tx.account_id not in allowed_accounts:continue
        if start and tx.booking_date<start:continue
        if end and tx.booking_date>end:continue
        baseline=json.loads(a.baseline_json or "{}");observed=json.loads(a.observed_json or "{}")
        median=Decimal(str(baseline.get("median","0")));amount=Decimal(str(observed.get("amount","0")))
        delta=max(Decimal("0"),amount-median)
        pct=None if median<=0 else (delta/median*Decimal("100"))
        out.append({
            "id":a.id,"transaction_id":a.transaction_id,"type":a.anomaly_type,"explanation":a.explanation,
            "confidence":str(a.confidence),"status":a.status,
            "transaction":None if tx is None else {
                "booking_date":tx.booking_date,"description":tx.description_raw,"merchant":tx.merchant_raw,
                "amount":str(tx.amount),"currency":tx.currency,"category_id":tx.category_id,
            },
            "baseline":{"typical_amount":str(median),"difference":str(delta),"difference_pct":None if pct is None else str(pct.quantize(Decimal("0.1")))},
        })
    return out

@router.patch("/anomalies/{anomaly_id}")
def update_anomaly(anomaly_id:str,p:AnomalyStatusIn,db:Session=Depends(dbdep)):
    row=db.get(Anomaly,anomaly_id)
    if not row:raise HTTPException(404,"Anomaly not found")
    row.status=p.status;db.commit();return {"id":row.id,"status":row.status}
@router.get("/reconciliation")
def reconcile(db:Session=Depends(dbdep)):return {"issues":reconciliation(db)}
@router.get("/calendar")
def calendar(start:date|None=None,end:date|None=None,db:Session=Depends(dbdep),account_id:str|None=None,account_type:str|None=None):
    start=start or date.today();end=end or start+timedelta(days=90);return {"events":events(db,start,end,account_id,account_type)}
@router.get("/search")
def search(q:str,db:Session=Depends(dbdep),start:date|None=None,end:date|None=None,account_id:str|None=None,account_type:str|None=None):
    if len(q)<2:raise HTTPException(400,"Query too short")
    return global_search(db,q,start=start,end=end,account_id=account_id,account_type=account_type)
@router.get("/export/json")
def export_data(db:Session=Depends(dbdep)):return export_json(db)
@router.get("/export/transactions.csv")
def export_tx(db:Session=Depends(dbdep)):return Response(transactions_csv(db),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=financito-transactions.csv"})
@router.post("/demo/seed")
def demo(db:Session=Depends(dbdep)):
    try:r=seed(db);db.commit();return r
    except ValueError as e:raise HTTPException(409,str(e))
@router.post("/backtest/ma")
def backtest(prices:list[float],short:int=20,long:int=60,fee_bps:float=5):
    try:return backtest_ma(prices,short,long,fee_bps)
    except ValueError as e:raise HTTPException(400,str(e))
@router.post("/planning/amortize-vs-invest")
def planning(principal:float,debt_rate:float,investment_return:float,horizon_years:int,tax_rate:float=0):return amortize_vs_invest(principal,debt_rate,investment_return,horizon_years,tax_rate)
@router.post("/recommendation/score")
def recommendation(fundamentals:float|None=None,valuation:float|None=None,growth:float|None=None,quality:float|None=None,momentum:float|None=None,risk:float|None=None,portfolio_fit:float|None=None):return score(fundamentals,valuation,growth,quality,momentum,risk,portfolio_fit)
@router.get("/graph")
def graph(db:Session=Depends(dbdep)):
    edges=db.scalars(select(EntityLink)).all();return {"edges":[{"from":{"type":e.from_type,"id":e.from_id},"relation":e.relation_type,"to":{"type":e.to_type,"id":e.to_id},"confidence":str(e.confidence)} for e in edges]}
