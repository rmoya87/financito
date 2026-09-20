from __future__ import annotations
from datetime import date
from decimal import Decimal
import json
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .domain.risk import risk_metrics
from .models import Commitment,Contract,DecisionCase,Transaction
from .models_extended import Asset,CostCenter,CostCenterLink,CoverageFact,DecisionAlternative,DecisionOutcome,InsurancePolicy,Liability,NewsItem
from .models_analytics import Benefit,CoverageRequirement,LinkedProduct,ModelEvaluationRun
from .providers.crypto import CoinGeckoDemoProvider
from .providers.fundamentals import SecFundamentalsProvider
from .providers.macro import EcbMacroProvider
from .providers.news import GdeltNewsProvider
from .services.market_data import history as market_history,portfolio_exposure,refresh_history,refresh_security,security_risk
from .services.news_analysis import analyze_all,analyze_item,local_news
from .services.portfolio_analysis import portfolio_fit,portfolio_performance
from .services.decision_context import live_decision_context

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

class CostCenterIn(BaseModel):
    name:str;center_type:str="life_area";parent_id:str|None=None;metadata:dict={}
class CostLinkIn(BaseModel):
    cost_center_id:str;entity_type:str;entity_id:str;allocation_percentage:Decimal=Decimal("100")
class CoverageRequirementIn(BaseModel):
    insurance_type:str|None=None
    coverage_type:str
    minimum_limit:Decimal|None=None
    currency:str="EUR"
    notes:str|None=None
    enabled:bool=True

class BenefitIn(BaseModel):
    contract_id:str|None=None;name:str;benefit_type:str;theoretical_value:Decimal=Decimal("0");realized_value:Decimal=Decimal("0");user_adjusted_value:Decimal|None=None;period:str="annual"
class LinkedProductIn(BaseModel):
    parent_product_type:str;parent_product_id:str;linked_product_type:str;linked_product_id:str;discount_value:Decimal=Decimal("0");discount_unit:str="currency";conditions:str=""
class DecisionIn(BaseModel):
    decision_type:str;question:str;current_state:dict={};assumptions:dict={};constraints:dict={}
class DecisionStatusIn(BaseModel):
    status:str=Field(pattern="^(draft|evaluating|decided|closed|cancelled)$")

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
@router.get("/cost-centers/{center_id}/summary")
def cost_center_summary(center_id:str,db:Session=Depends(dbdep)):
    center=db.get(CostCenter,center_id)
    if not center:raise HTTPException(404,"Cost center not found")
    links=db.scalars(select(CostCenterLink).where(CostCenterLink.cost_center_id==center_id)).all()
    observed=Decimal("0");annual=Decimal("0");reference_assets=Decimal("0");reference_debt=Decimal("0");unpriced=[]
    for link in links:
        factor=link.allocation_percentage/Decimal("100")
        if link.entity_type=="transaction":
            row=db.get(Transaction,link.entity_id)
            if row:observed+=(-row.amount)*factor if row.amount<0 else row.amount*Decimal("-1")*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        elif link.entity_type=="contract":
            row=db.get(Contract,link.entity_id)
            if row and row.annual_cost is not None:annual+=row.annual_cost*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        elif link.entity_type=="insurance_policy":
            row=db.get(InsurancePolicy,link.entity_id)
            if row:annual+=row.annual_premium*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        elif link.entity_type=="commitment":
            row=db.get(Commitment,link.entity_id)
            if row:annual+=row.amount*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        elif link.entity_type=="asset":
            row=db.get(Asset,link.entity_id)
            if row:reference_assets+=row.current_value*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        elif link.entity_type=="liability":
            row=db.get(Liability,link.entity_id)
            if row:reference_debt+=row.outstanding_amount*factor
            else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
        else:unpriced.append({"type":link.entity_type,"id":link.entity_id})
    return {"id":center.id,"name":center.name,"observed_linked_spend":str(observed),"annual_linked_commitments":str(annual),"reference_asset_value":str(reference_assets),"reference_debt":str(reference_debt),"unpriced_links":unpriced}

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
@router.get("/decisions/{decision_id}")
def decision_detail(decision_id:str,db:Session=Depends(dbdep)):
    row=db.get(DecisionCase,decision_id)
    if not row:raise HTTPException(404,"Decision not found")
    alternatives=db.scalars(select(DecisionAlternative).where(DecisionAlternative.decision_case_id==decision_id).order_by(DecisionAlternative.created_at)).all()
    outcomes=db.scalars(select(DecisionOutcome).where(DecisionOutcome.decision_case_id==decision_id).order_by(DecisionOutcome.created_at)).all()
    return {
        "id":row.id,"type":row.decision_type,"question":row.question,"status":row.status,
        "current_state":json.loads(row.current_state_json),"live_current_state":live_decision_context(db),"assumptions":json.loads(row.assumptions_json),"constraints":json.loads(row.constraints_json),
        "alternatives":[{"id":a.id,"name":a.name,"one_off_cost":str(a.one_off_cost),"monthly_cost":str(a.monthly_cost),"expected_benefit":str(a.expected_benefit),"net_benefit":str(a.net_benefit),"break_even_months":None if a.break_even_months is None else str(a.break_even_months),"risk_level":a.risk_level,"horizon_results":json.loads(a.horizon_results_json),"uncertainties":json.loads(a.uncertainties_json)} for a in alternatives],
        "outcomes":[{"id":o.id,"selected_alternative_id":o.selected_alternative_id,"observation_start":o.observation_start,"observation_end":o.observation_end,"expected":json.loads(o.expected_impact_json),"observed":json.loads(o.observed_impact_json),"variance":json.loads(o.variance_json),"explanation":o.explanation,"data_completeness":str(o.data_completeness)} for o in outcomes],
    }

@router.patch("/decisions/{decision_id}")
def update_decision(decision_id:str,p:DecisionStatusIn,db:Session=Depends(dbdep)):
    row=db.get(DecisionCase,decision_id)
    if not row:raise HTTPException(404,"Decision not found")
    row.status=p.status;db.commit();return {"id":row.id,"status":row.status}

@router.post("/decisions")
def add_decision(p:DecisionIn,db:Session=Depends(dbdep)):
    live=live_decision_context(db)
    snapshot={"captured_from":"live_financito_data","context":live}
    if p.current_state:snapshot["user_input"]=p.current_state
    r=DecisionCase(decision_type=p.decision_type,question=p.question,current_state_json=json.dumps(snapshot),assumptions_json=json.dumps(p.assumptions),constraints_json=json.dumps(p.constraints),calculation_version="real-context-v1",status="draft");db.add(r);db.commit();return {"id":r.id}
@router.delete("/decisions/{decision_id}")
def delete_decision(decision_id:str,db:Session=Depends(dbdep)):
    row=db.get(DecisionCase,decision_id)
    if not row:raise HTTPException(404,"Decision not found")
    db.execute(delete(DecisionOutcome).where(DecisionOutcome.decision_case_id==decision_id))
    db.execute(delete(DecisionAlternative).where(DecisionAlternative.decision_case_id==decision_id))
    db.delete(row);db.commit()
    return {"deleted":decision_id}

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
        row=NewsItem(canonical_url=url,source=item.get("source") or "GDELT",headline=item.get("title") or "",published_at=dt,summary=None,reliability=Decimal("0.5"));db.add(row);db.flush();analyze_item(db,row);inserted+=1
    db.commit();return {"inserted":inserted,"discovered":len(items)}


@router.get("/market/security/{security_id}/history")
def security_history(security_id:str,db:Session=Depends(dbdep)):
    return {"security_id":security_id,"rows":market_history(db,security_id)}

@router.post("/market/security/{security_id}/refresh")
def security_refresh(security_id:str,include_history:bool=True,db:Session=Depends(dbdep)):
    try:
        quote=refresh_security(db,security_id)
        history_result=refresh_history(db,security_id) if include_history else None
        db.commit();return {"quote":quote,"history":history_result}
    except ValueError as e:
        db.rollback();raise HTTPException(400,str(e))
    except Exception as e:
        db.rollback();raise HTTPException(503,str(e))

@router.get("/market/security/{security_id}/risk")
def market_security_risk(security_id:str,db:Session=Depends(dbdep)):
    return security_risk(db,security_id)

@router.get("/portfolios/{portfolio_id}/exposure")
def market_portfolio_exposure(portfolio_id:str,db:Session=Depends(dbdep)):
    try:return portfolio_exposure(db,portfolio_id)
    except ValueError as e:raise HTTPException(404,str(e))

@router.get("/crypto/metrics/{coin_id}")
def crypto_metrics(coin_id:str,vs_currency:str="eur",days:int=90):
    if days<2 or days>3650:raise HTTPException(400,"days must be 2..3650")
    try:
        provider=CoinGeckoDemoProvider()
        chart=provider.market_chart(coin_id,vs_currency,days)
        prices=[float(x[1]) for x in chart.get("prices",[]) if len(x)>1]
        return {"coin_id":coin_id,"vs_currency":vs_currency,"days":days,"metrics":risk_metrics(prices,periods_per_year=365),"observations":len(prices),"provider":"CoinGecko"}
    except Exception as e:raise HTTPException(503,str(e))


@router.get("/coverage-requirements")
def coverage_requirements(db:Session=Depends(dbdep)):
    rows=db.scalars(select(CoverageRequirement).order_by(CoverageRequirement.coverage_type)).all()
    return [{"id":r.id,"insurance_type":r.insurance_type,"coverage_type":r.coverage_type,"minimum_limit":None if r.minimum_limit is None else str(r.minimum_limit),"currency":r.currency,"notes":r.notes,"enabled":r.enabled} for r in rows]

@router.post("/coverage-requirements")
def add_coverage_requirement(p:CoverageRequirementIn,db:Session=Depends(dbdep)):
    row=CoverageRequirement(**p.model_dump());db.add(row);db.commit();return {"id":row.id}

@router.delete("/coverage-requirements/{requirement_id}")
def delete_coverage_requirement(requirement_id:str,db:Session=Depends(dbdep)):
    row=db.get(CoverageRequirement,requirement_id)
    if not row:raise HTTPException(404,"Coverage requirement not found")
    db.delete(row);db.commit();return {"deleted":requirement_id}

@router.get("/coverage/gaps")
def coverage_gaps(db:Session=Depends(dbdep)):
    today=date.today()
    requirements=db.scalars(select(CoverageRequirement).where(CoverageRequirement.enabled.is_(True))).all()
    facts=db.scalars(select(CoverageFact).where(CoverageFact.user_verified.is_(True))).all()
    policies={p.id:p for p in db.scalars(select(InsurancePolicy)).all()}
    gaps=[];covered=[]
    for req in requirements:
        eligible=[]
        for fact in facts:
            if fact.coverage_type.strip().lower()!=req.coverage_type.strip().lower():continue
            if fact.effective_from and fact.effective_from>today:continue
            if fact.effective_to and fact.effective_to<today:continue
            if req.insurance_type:
                policy=policies.get(fact.insurance_policy_id)
                if not policy or policy.insurance_type!=req.insurance_type:continue
            eligible.append(fact)
        limits=[f.limit_amount for f in eligible if f.limit_amount is not None]
        if not eligible:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"missing_verified_coverage","minimum_limit":None if req.minimum_limit is None else str(req.minimum_limit)})
        elif req.minimum_limit is not None and not limits:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"limit_unknown","minimum_limit":str(req.minimum_limit)})
        elif req.minimum_limit is not None and max(limits)<req.minimum_limit:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"limit_below_requirement","minimum_limit":str(req.minimum_limit),"best_verified_limit":str(max(limits))})
        else:
            covered.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"matching_coverages":len(eligible),"best_verified_limit":None if not limits else str(max(limits))})
    return {"gaps":gaps,"covered":covered,"requirements":len(requirements)}


@router.get("/news/local")
def news_local(limit:int=100,db:Session=Depends(dbdep)):
    return {"items":local_news(db,limit)}

@router.post("/news/analyze")
def news_analyze(limit:int=500,db:Session=Depends(dbdep)):
    result=analyze_all(db,limit);db.commit();return result


@router.get("/portfolios/{portfolio_id}/performance")
def portfolio_performance_route(portfolio_id:str,db:Session=Depends(dbdep)):
    try:return portfolio_performance(db,portfolio_id)
    except ValueError as exc:raise HTTPException(404,str(exc))

@router.get("/portfolios/{portfolio_id}/fit/{security_id}")
def portfolio_fit_route(portfolio_id:str,security_id:str,proposed_weight:Decimal=Decimal("0.10"),db:Session=Depends(dbdep)):
    try:return portfolio_fit(db,portfolio_id,security_id,proposed_weight)
    except ValueError as exc:raise HTTPException(400,str(exc))
