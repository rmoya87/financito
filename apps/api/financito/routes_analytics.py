from __future__ import annotations
from datetime import date,timedelta
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .domain.analytics import detect_anomalies,detect_recurring
from .domain.backtest import amortize_vs_invest,backtest_ma
from .domain.recommendations import score
from .models_analytics import Anomaly,EntityLink,RecurringSeries
from .services.calendar import events
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
@router.get("/recurring")
def recurring(db:Session=Depends(dbdep)):return [{"id":r.id,"merchant":r.merchant_normalized,"cadence":r.cadence,"expected_amount":str(r.expected_amount),"next_expected_date":r.next_expected_date,"confidence":str(r.confidence)} for r in db.scalars(select(RecurringSeries)).all()]
@router.get("/anomalies")
def anomalies(db:Session=Depends(dbdep)):return [{"id":a.id,"transaction_id":a.transaction_id,"type":a.anomaly_type,"explanation":a.explanation,"confidence":str(a.confidence),"status":a.status} for a in db.scalars(select(Anomaly)).all()]
@router.get("/reconciliation")
def reconcile(db:Session=Depends(dbdep)):return {"issues":reconciliation(db)}
@router.get("/calendar")
def calendar(start:date|None=None,end:date|None=None,db:Session=Depends(dbdep)):
    start=start or date.today();end=end or start+timedelta(days=90);return {"events":events(db,start,end)}
@router.get("/search")
def search(q:str,db:Session=Depends(dbdep)):
    if len(q)<2:raise HTTPException(400,"Query too short")
    return global_search(db,q)
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
