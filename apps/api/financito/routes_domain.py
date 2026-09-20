from __future__ import annotations
from datetime import date
from decimal import Decimal
import json
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .domain.risk import risk_metrics
from .models import DecisionCase
from .models_extended import CostCenter,CostCenterLink,DecisionAlternative,DecisionOutcome,NewsItem
from .models_analytics import Benefit,LinkedProduct,ModelEvaluationRun
from .providers.crypto import CoinGeckoDemoProvider
from .providers.fundamentals import SecFundamentalsProvider
from .providers.macro import EcbMacroProvider
from .providers.news import GdeltNewsProvider

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

class CostCenterIn(BaseModel):
    name:str;center_type:str="life_area";parent_id:str|None=None;metadata:dict={}
class CostLinkIn(BaseModel):
    cost_center_id:str;entity_type:str;entity_id:str;allocation_percentage:Decimal=Decimal("100")
class BenefitIn(BaseModel):
    contract_id:str|None=None;name:str;benefit_type:str;theoretical_value:Decimal=Decimal("0");realized_value:Decimal=Decimal("0");user_adjusted_value:Decimal|None=None;period:str="annual"
class LinkedProductIn(BaseModel):
    parent_product_type:str;parent_product_id:str;linked_product_type:str;linked_product_id:str;discount_value:Decimal=Decimal("0");discount_unit:str="currency";conditions:str=""
class DecisionIn(BaseModel):
    decision_type:str;question:str;current_state:dict={};assumptions:dict={};constraints:dict={}
class AlternativeIn(BaseModel):
    name:str;one_off_cost:Decimal=Decimal("0");monthly_cost:Decimal=Decimal("0");expected_benefit:Decimal=Decimal("0");risk_level:str="unknown";horizon_results:dict={};uncertainties:list=[]
class OutcomeIn(BaseModel):
    selected_alternative_id:str|None=None;observation_start:date;observation_end:date;expected_impact:dict={};observed_impact:dict={};explanation:str|None=None;data_completeness:Decimal=Decimal("0")
class EvalIn(BaseModel):
    model_type:str;candidate_version:str;baseline_version:str|None=None;dataset_version:str;metrics:dict;passed_gate:bool
class RiskIn(BaseModel):
    prices:list[float]=Field(min_length=3);periods_per_year:int=252;risk_free_rate:float=0

@router.get("/cost-centers")
def cost_centers(db:Session=Depends(dbdep)):
    centers=db.scalars(select(CostCenter).order_by(CostCenter.name)).all()
    links=db.scalars(select(CostCenterLink)).all()
    return [{"id":c.id,"name":c.name,"type":c.center_type,"parent_id":c.parent_id,"links":[{"entity_type":l.entity_type,"entity_id":l.entity_id,"allocation_percentage":str(l.allocation_percentage)} for l in links if l.cost_center_id==c.id]} for c in centers]
@router.post("/cost-centers")
def add_center(p:CostCenterIn,db:Session=Depends(dbdep)):
    r=CostCenter(name=p.name,center_type=p.center_type,parent_id=p.parent_id,metadata_json=json.dumps(p.metadata));db.add(r);db.commit();return {"id":r.id}
@router.post("/cost-center-links")
def add_center_link(p:CostLinkIn,db:Session=Depends(dbdep)):
    if not db.get(CostCenter,p.cost_center_id):raise HTTPException(404,"Cost center not found")
    r=CostCenterLink(**p.model_dump());db.add(r);db.commit();return {"id":r.id}

@router.get("/benefits")
def benefits(db:Session=Depends(dbdep)):
    return [{"id":r.id,"contract_id":r.contract_id,"name":r.name,"type":r.benefit_type,"theoretical_value":str(r.theoretical_value),"realized_value":str(r.realized_value),"user_adjusted_value":None if r.user_adjusted_value is None else str(r.user_adjusted_value)} for r in db.scalars(select(Benefit)).all()]
@router.post("/benefits")
def add_benefit(p:BenefitIn,db:Session=Depends(dbdep)):r=Benefit(**p.model_dump());db.add(r);db.commit();return {"id":r.id}
@router.post("/linked-products")
def add_linked(p:LinkedProductIn,db:Session=Depends(dbdep)):r=LinkedProduct(**p.model_dump());db.add(r);db.commit();return {"id":r.id}

@router.get("/decisions")
def decisions(db:Session=Depends(dbdep)):
    return [{"id":r.id,"type":r.decision_type,"question":r.question,"status":r.status,"created_at":r.created_at} for r in db.scalars(select(DecisionCase).order_by(DecisionCase.created_at.desc())).all()]
@router.post("/decisions")
def add_decision(p:DecisionIn,db:Session=Depends(dbdep)):
    r=DecisionCase(decision_type=p.decision_type,question=p.question,current_state_json=json.dumps(p.current_state),assumptions_json=json.dumps(p.assumptions),constraints_json=json.dumps(p.constraints),calculation_version="v1",status="draft");db.add(r);db.commit();return {"id":r.id}
@router.post("/decisions/{decision_id}/alternatives")
def add_alt(decision_id:str,p:AlternativeIn,db:Session=Depends(dbdep)):
    if not db.get(DecisionCase,decision_id):raise HTTPException(404,"Decision not found")
    net=p.expected_benefit-p.one_off_cost-p.monthly_cost*Decimal("12");monthly=max(Decimal("0"),p.expected_benefit/Decimal("12")-p.monthly_cost);be=None if monthly<=0 else p.one_off_cost/monthly
    r=DecisionAlternative(decision_case_id=decision_id,name=p.name,one_off_cost=p.one_off_cost,monthly_cost=p.monthly_cost,expected_benefit=p.expected_benefit,net_benefit=net,break_even_months=be,risk_level=p.risk_level,horizon_results_json=json.dumps(p.horizon_results),uncertainties_json=json.dumps(p.uncertainties));db.add(r);db.commit();return {"id":r.id,"net_benefit":str(net),"break_even_months":None if be is None else str(be)}
@router.post("/decisions/{decision_id}/outcomes")
def add_outcome(decision_id:str,p:OutcomeIn,db:Session=Depends(dbdep)):
    if not db.get(DecisionCase,decision_id):raise HTTPException(404,"Decision not found")
    variance={}
    for k,v in p.expected_impact.items():
        if isinstance(v,(int,float)) and isinstance(p.observed_impact.get(k),(int,float)):variance[k]=p.observed_impact[k]-v
    r=DecisionOutcome(decision_case_id=decision_id,selected_alternative_id=p.selected_alternative_id,observation_start=p.observation_start,observation_end=p.observation_end,expected_impact_json=json.dumps(p.expected_impact),observed_impact_json=json.dumps(p.observed_impact),variance_json=json.dumps(variance),explanation=p.explanation,data_completeness=p.data_completeness);db.add(r);db.commit();return {"id":r.id,"variance":variance}

@router.post("/model-evaluations")
def model_eval(p:EvalIn,db:Session=Depends(dbdep)):
    r=ModelEvaluationRun(model_type=p.model_type,candidate_version=p.candidate_version,baseline_version=p.baseline_version,dataset_version=p.dataset_version,metrics_json=json.dumps(p.metrics),passed_gate=p.passed_gate);db.add(r);db.commit();return {"id":r.id,"passed_gate":r.passed_gate}
@router.get("/model-evaluations")
def model_evals(db:Session=Depends(dbdep)):
    return [{"id":r.id,"model_type":r.model_type,"candidate_version":r.candidate_version,"baseline_version":r.baseline_version,"dataset_version":r.dataset_version,"metrics":json.loads(r.metrics_json),"passed_gate":r.passed_gate,"created_at":r.created_at} for r in db.scalars(select(ModelEvaluationRun).order_by(ModelEvaluationRun.created_at.desc())).all()]

@router.post("/risk/calculate")
def risk(p:RiskIn):return risk_metrics(p.prices,p.periods_per_year,p.risk_free_rate)

@router.get("/fundamentals/sec/{cik}")
def sec_facts(cik:str):
    try:
        provider=SecFundamentalsProvider();data=provider.companyfacts(cik)
        concepts=["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","NetIncomeLoss","EarningsPerShareDiluted","CashAndCashEquivalentsAtCarryingValue","LongTermDebtCurrent","LongTermDebtNoncurrent"]
        return {"cik":data.get("cik"),"entity_name":data.get("entityName"),"facts":provider.latest_us_gaap(data,concepts),"provider":"SEC EDGAR"}
    except Exception as e:raise HTTPException(503,str(e))
@router.get("/macro/ecb/{flow}/{key:path}")
def ecb_series(flow:str,key:str,start:str|None=None,end:str|None=None,last_n:int|None=30):
    try:return {"provider":"ECB","rows":EcbMacroProvider().series(flow,key,start,end,last_n)}
    except Exception as e:raise HTTPException(503,str(e))
@router.get("/crypto/price")
def crypto_price(ids:str,vs_currency:str="eur"):
    try:return {"provider":"CoinGecko","data":CoinGeckoDemoProvider().simple_price([x.strip() for x in ids.split(",") if x.strip()],vs_currency)}
    except Exception as e:raise HTTPException(503,str(e))

@router.post("/news/ingest")
def ingest_news(q:str,db:Session=Depends(dbdep)):
    if len(q)<2:raise HTTPException(400,"Query too short")
    try:items=GdeltNewsProvider().search(q,30)
    except Exception as e:raise HTTPException(503,str(e))
    inserted=0
    for item in items:
        url=item.get("url")
        if not url or db.scalar(select(NewsItem.id).where(NewsItem.canonical_url==url)):continue
        published=item.get("published_at") or ""
        try:
            from datetime import datetime,timezone
            dt=datetime.strptime(published[:14],"%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc) if "T" in published else datetime.now(timezone.utc)
        except Exception:
            from datetime import datetime,timezone
            dt=datetime.now(timezone.utc)
        db.add(NewsItem(canonical_url=url,source=item.get("source") or "GDELT",headline=item.get("title") or "",published_at=dt,summary=None,reliability=Decimal("0.5")));inserted+=1
    db.commit();return {"inserted":inserted,"discovered":len(items)}
