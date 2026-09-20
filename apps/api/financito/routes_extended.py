from __future__ import annotations
from datetime import date
from decimal import Decimal,ROUND_CEILING
import json
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Account,Contract,FinancialGoal,Mortgage,Portfolio,Security
from .models_extended import Asset,BackupRecord,CoverageFact,InsurancePolicy,Liability,RepairIssue,Trade,TrackedAsset
from .models_analytics import EntityLink
from .schemas_extended import AssetCreate,AssetSimulationStart,BackupCreate,BackupRestore,ChatRequest,ContractCreate,CoverageCompareRequest,CoverageCreate,CorporateActionCreate,GoalCreate,GoalProgressUpdate,InsuranceCreate,LiabilityCreate,MortgageProfileCreate,MortgageProfileUpdate,PortfolioCreate,RagSearchRequest,SecurityCreate,StoredMortgagePrepaymentRequest,StoredMortgageRatePathRequest,StoredMortgageScenarioRequest,StressRequest,TaxEstimateRequest,TaxProfileUpdate,TrackedAssetCreate,TradeCreate
from .domain.portfolio import apply_trade,portfolio_summary
from .domain.engines import MortgageEngine,MortgagePrepaymentEngine,MortgageRatePathEngine
from .domain.stress import run_stress
from .services.backup import create_backup,stage_restore
from .services.chat import answer
from .services.contracts import compare_coverages,refresh_contract_actions,scan_coverage_overlaps
from .services.import_formats import import_statement
from .services.transaction_ops import detect_internal_transfers,detect_refunds
from .services.insurance_analysis import insurance_verdict
from .services.rag import index_document_chunks,search
from .services.repair import repair,scan
from .services.tax import estimate,get_profile,profile_dict,upsert_profile
from .services.wealth import summary as wealth_summary
from .services.financial_analytics import cash_flow
from .services.snapshots import record_snapshot
from .services.decision_context import live_decision_context,mortgage_row
from .services.contractual_costs import resolve_prepayment_penalty,switching_readiness
from .services.market_research import scan_public_market
from .services.investment_tracking import remove_tracking,save_tracked_asset,simulation_history,start_simulation,tracked_assets
from .services.broker_import import import_broker_csv
from .services.corporate_actions import add_action,list_actions
from .providers.market import quote_with_free_fallback
from .providers.news import GdeltNewsProvider
router=APIRouter(prefix="/api/v1")

def dbdep():
    db=SessionLocal()
    try:yield db
    finally:db.close()

def _document_sources(db:Session,to_type:str)->dict[str,str]:
    links=db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
        EntityLink.to_type==to_type,
    )).all()
    return {link.to_id:link.from_id for link in links}

def _document_sources_multi(db:Session,to_type:str)->dict[str,list[str]]:
    links=db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
        EntityLink.to_type==to_type,
    )).all()
    result:dict[str,list[str]]={}
    for link in links:result.setdefault(link.to_id,[]).append(link.from_id)
    return result

@router.get("/decision-lab/market-scan")
def decision_lab_market_scan(db:Session=Depends(dbdep)):
    return scan_public_market(db)

@router.get("/decision-lab/switching-readiness")
def decision_lab_switching_readiness(mortgage_id:str|None=None,db:Session=Depends(dbdep)):
    return switching_readiness(db,mortgage_id)

@router.get("/decision-lab/context")
def decision_lab_context(db:Session=Depends(dbdep)):
    return live_decision_context(db)

@router.get("/mortgages")
def mortgages(db:Session=Depends(dbdep)):
    sources=_document_sources(db,"mortgage")
    return [{**mortgage_row(r),"source_document_id":sources.get(r.id)} for r in db.scalars(select(Mortgage).order_by(Mortgage.updated_at.desc())).all()]

@router.post("/mortgages")
def add_mortgage(p:MortgageProfileCreate,db:Session=Depends(dbdep)):
    r=Mortgage(**p.model_dump())
    db.add(r);db.flush()
    record_snapshot(db,"mortgage",r.id,{
        "remaining_principal":str(r.remaining_principal),
        "nominal_rate":str(r.nominal_rate),
        "monthly_payment":str(r.monthly_payment),
        "remaining_months":r.remaining_months,
        "early_repayment_fee":None if r.early_repayment_fee is None else str(r.early_repayment_fee),
        "currency":r.currency,
    },source="mortgage_created")
    db.commit();return mortgage_row(r)

@router.patch("/mortgages/{mortgage_id}")
def update_mortgage(mortgage_id:str,p:MortgageProfileUpdate,db:Session=Depends(dbdep)):
    r=db.get(Mortgage,mortgage_id)
    if not r:raise HTTPException(404,"Mortgage not found")
    for key,value in p.model_dump().items():setattr(r,key,value)
    db.flush()
    record_snapshot(db,"mortgage",r.id,{
        "remaining_principal":str(r.remaining_principal),
        "nominal_rate":str(r.nominal_rate),
        "monthly_payment":str(r.monthly_payment),
        "remaining_months":r.remaining_months,
        "early_repayment_fee":None if r.early_repayment_fee is None else str(r.early_repayment_fee),
        "currency":r.currency,
    },source="mortgage_updated")
    db.commit();return mortgage_row(r)

@router.post("/decision-lab/mortgage/current")
def mortgage_current(p:StoredMortgageScenarioRequest,db:Session=Depends(dbdep)):
    r=db.get(Mortgage,p.mortgage_id)
    if not r:raise HTTPException(404,"Mortgage not found")
    result=MortgageEngine.amortization(r.remaining_principal,r.nominal_rate,r.remaining_months)
    return {
        "mortgage":mortgage_row(r),
        "calculated_monthly_payment":str(result.monthly_payment),
        "saved_monthly_payment":str(r.monthly_payment),
        "monthly_payment_difference":str(result.monthly_payment-r.monthly_payment),
        "total_payments":str(result.total_payments),
        "total_interest":str(result.total_interest),
        "source":"saved_mortgage",
    }

@router.post("/decision-lab/mortgage/prepayment")
def mortgage_prepayment_real(p:StoredMortgagePrepaymentRequest,db:Session=Depends(dbdep)):
    r=db.get(Mortgage,p.mortgage_id)
    if not r:raise HTTPException(404,"Mortgage not found")
    penalty=resolve_prepayment_penalty(db,r,p.extra_payment)
    if penalty["amount"] is None:
        raise HTTPException(409,"Falta confirmar en la documentación la comisión/fórmula de amortización anticipada")
    result=MortgagePrepaymentEngine.compare(
        r.remaining_principal,r.nominal_rate,r.remaining_months,p.extra_payment,penalty["amount"]
    )
    return {
        "mortgage":mortgage_row(r),
        **{k:(str(v) if not isinstance(v,int) else v) for k,v in result.__dict__.items()},
        "source":"saved_mortgage+confirmed_contract_evidence",
        "penalty_trace":{
            "status":penalty["status"],
            "amount":str(penalty["amount"]),
            "formula":penalty["formula"],
            "source":penalty["source"],
        },
        "assumption":{"extra_payment":str(p.extra_payment)},
    }

@router.post("/decision-lab/mortgage/rate-path")
def mortgage_rate_path_real(p:StoredMortgageRatePathRequest,db:Session=Depends(dbdep)):
    r=db.get(Mortgage,p.mortgage_id)
    if not r:raise HTTPException(404,"Mortgage not found")
    steps=[]
    for raw in p.rate_steps:
        try:
            month=int(raw["month"]);rate=Decimal(str(raw["annual_rate"]))
        except Exception:
            raise HTTPException(400,"Invalid rate step")
        steps.append((month,rate))
    result=MortgageRatePathEngine.simulate(r.remaining_principal,r.remaining_months,r.nominal_rate,steps)
    return {
        "mortgage":mortgage_row(r),
        "total_payments":str(result.total_payments),
        "total_interest":str(result.total_interest),
        "min_monthly_payment":str(result.min_monthly_payment),
        "max_monthly_payment":str(result.max_monthly_payment),
        "final_balance":str(result.final_balance),
        "segments":[{"start_month":s.start_month,"annual_rate":str(s.annual_rate),"monthly_payment":str(s.monthly_payment),"end_balance":str(s.end_balance)} for s in result.segments],
        "source":"saved_mortgage",
        "notice":"La situación inicial procede de la hipoteca guardada. Los cambios de tipo son supuestos introducidos por el usuario, no una predicción.",
    }

@router.get("/tracked-assets")
def tracked_assets_route(db:Session=Depends(dbdep)):
    return tracked_assets(db)

@router.post("/tracked-assets")
def tracked_asset_add(p:TrackedAssetCreate,db:Session=Depends(dbdep)):
    try:
        result=save_tracked_asset(
            db,
            asset_class=p.asset_class,
            name=p.name,
            identifier=p.identifier,
            owned=p.owned,
            portfolio_id=p.portfolio_id,
            quantity=p.quantity,
            purchase_price=p.purchase_price,
            purchase_date=p.purchase_date,
            fees=p.fees,
            fx_rate=p.fx_rate,
            currency=p.currency,
            provider_asset_id=p.provider_asset_id,
            notes=p.notes,
        )
        db.commit();return result
    except ValueError as exc:
        db.rollback();raise HTTPException(409,str(exc))

@router.post("/tracked-assets/{security_id}/simulation")
def tracked_asset_simulation(security_id:str,p:AssetSimulationStart,db:Session=Depends(dbdep)):
    from .services.market_data import refresh_history,refresh_security
    if not db.get(Security,security_id):raise HTTPException(404,"Security not found")
    try:
        refresh_security(db,security_id)
        refresh_history(db,security_id)
        result=start_simulation(db,security_id,p.amount)
        db.commit();return result
    except ValueError as exc:
        db.rollback();raise HTTPException(400,str(exc))
    except Exception as exc:
        db.rollback();raise HTTPException(503,str(exc))

@router.get("/tracked-assets/{security_id}/simulation-history")
def tracked_asset_simulation_history(security_id:str,db:Session=Depends(dbdep)):
    if not db.get(Security,security_id):raise HTTPException(404,"Security not found")
    return simulation_history(db,security_id)

@router.delete("/tracked-assets/{security_id}")
def tracked_asset_delete(security_id:str,db:Session=Depends(dbdep)):
    if not db.get(Security,security_id):raise HTTPException(404,"Security not found")
    result=remove_tracking(db,security_id);db.commit();return result

@router.post("/tracked-assets/{security_id}/unfollow")
def tracked_asset_unfollow(security_id:str,db:Session=Depends(dbdep)):
    """Explicit action alias used by the UI for watch-list removal."""
    return tracked_asset_delete(security_id,db)

@router.post("/tracked-assets/refresh-all")
def tracked_assets_refresh_all(db:Session=Depends(dbdep)):
    from .services.market_data import refresh_security
    rows=tracked_assets(db)
    refreshed=[];failed=[]
    for item in rows:
        try:
            quote=refresh_security(db,item["security_id"])
            refreshed.append({"security_id":item["security_id"],"quote":quote})
        except Exception as exc:
            failed.append({"security_id":item["security_id"],"error":str(exc)})
    db.commit()
    return {"refreshed":refreshed,"failed":failed,"assets":tracked_assets(db)}

@router.post("/tracked-assets/{security_id}/refresh")
def tracked_asset_refresh(security_id:str,include_history:bool=False,db:Session=Depends(dbdep)):
    from .services.market_data import refresh_security,refresh_history
    if not db.get(Security,security_id):raise HTTPException(404,"Security not found")
    try:
        quote=refresh_security(db,security_id)
        history_result=refresh_history(db,security_id) if include_history else None
        db.commit()
        security=db.get(Security,security_id)
        from .services.investment_tracking import security_summary
        return {"quote":quote,"history":history_result,"asset":security_summary(db,security)}
    except ValueError as exc:
        db.rollback();raise HTTPException(400,str(exc))
    except Exception as exc:
        db.rollback();raise HTTPException(503,str(exc))

@router.get("/wealth")
def wealth(db:Session=Depends(dbdep)):return wealth_summary(db)

@router.get("/wealth/details")
def wealth_details(db:Session=Depends(dbdep)):
    summary=wealth_summary(db)
    accounts=[{
        "id":row.id,
        "name":row.name,
        "institution_name":row.institution_name,
        "currency":row.currency,
        "balance":str(row.current_balance),
    } for row in db.scalars(select(Account).order_by(Account.name)).all()]
    assets=[{
        "id":row.id,
        "type":row.asset_type,
        "name":row.name,
        "value":str(row.current_value),
        "currency":row.currency,
        "valuation_date":row.valuation_date,
        "valuation_source":row.valuation_source,
        "ownership_percentage":str(row.ownership_percentage),
    } for row in db.scalars(select(Asset).order_by(Asset.asset_type,Asset.name)).all()]
    liabilities=[{
        "id":row.id,
        "type":row.liability_type,
        "name":row.name,
        "amount":str(row.outstanding_amount),
        "currency":row.currency,
        "annual_rate":None if row.annual_rate is None else str(row.annual_rate),
        "ownership_percentage":str(row.ownership_percentage),
    } for row in db.scalars(select(Liability).order_by(Liability.liability_type,Liability.name)).all()]
    mortgages=[{
        "id":row.id,
        "lender":row.lender,
        "remaining_principal":str(row.remaining_principal),
        "currency":row.currency,
        "interest_type":row.interest_type,
        "nominal_rate":str(row.nominal_rate),
        "monthly_payment":str(row.monthly_payment),
        "remaining_months":row.remaining_months,
    } for row in db.scalars(select(Mortgage).order_by(Mortgage.lender)).all()]
    contracts={row.id:row for row in db.scalars(select(Contract)).all()}
    policies=[]
    annual_insurance=Decimal("0")
    for row in db.scalars(select(InsurancePolicy).order_by(InsurancePolicy.insurance_type)).all():
        annual_insurance+=row.annual_premium
        contract=contracts.get(row.contract_id) if row.contract_id else None
        policies.append({
            "id":row.id,
            "insurance_type":row.insurance_type,
            "annual_premium":str(row.annual_premium),
            "currency":row.currency,
            "deductible":None if row.deductible is None else str(row.deductible),
            "provider":None if contract is None else contract.provider_name,
            "contract_id":row.contract_id,
        })
    investments=[row for row in tracked_assets(db) if row.get("owned")]
    return {
        "summary":summary,
        "accounts":accounts,
        "assets":assets,
        "liabilities":liabilities,
        "mortgages":mortgages,
        "investments":investments,
        "insurance":{"annual_premium_total":str(annual_insurance),"policies":policies},
    }
@router.get("/assets")
def assets(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.asset_type,"name":r.name,"value":str(r.current_value),"currency":r.currency,"valuation_date":r.valuation_date} for r in db.scalars(select(Asset).order_by(Asset.name)).all()]
@router.post("/assets")
def add_asset(p:AssetCreate,db:Session=Depends(dbdep)):
    r=Asset(**p.model_dump());db.add(r);db.flush()
    record_snapshot(db,"asset",r.id,{"value":str(r.current_value),"ownership_percentage":str(r.ownership_percentage),"currency":r.currency},r.valuation_date,"asset_created")
    db.commit();return {"id":r.id}
@router.get("/liabilities")
def liabilities(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.liability_type,"name":r.name,"amount":str(r.outstanding_amount),"currency":r.currency} for r in db.scalars(select(Liability).order_by(Liability.name)).all()]
@router.post("/liabilities")
def add_liability(p:LiabilityCreate,db:Session=Depends(dbdep)):
    r=Liability(**p.model_dump());db.add(r);db.flush()
    record_snapshot(db,"liability",r.id,{"outstanding_amount":str(r.outstanding_amount),"ownership_percentage":str(r.ownership_percentage),"currency":r.currency},source="liability_created")
    db.commit();return {"id":r.id}

@router.get("/contracts")
def contracts(db:Session=Depends(dbdep)):
    refresh_contract_actions(db);db.commit()
    sources=_document_sources_multi(db,"contract")
    rows=db.scalars(select(Contract).where(
        Contract.contract_type.notin_(["insurance","mortgage"])
    ).order_by(Contract.provider_name)).all()
    return [{"id":r.id,"provider_name":r.provider_name,"contract_type":r.contract_type,"renewal_date":r.renewal_date,"cancellation_notice_days":r.cancellation_notice_days,"early_exit_penalty":None if r.early_exit_penalty is None else str(r.early_exit_penalty),"annual_cost":None if r.annual_cost is None else str(r.annual_cost),"evidence_status":r.evidence_status,"source_document_id":(sources.get(r.id) or [None])[0],"source_document_ids":sources.get(r.id,[]),"document_count":len(sources.get(r.id,[]))} for r in rows]
@router.post("/contracts")
def add_contract(p:ContractCreate,db:Session=Depends(dbdep)):r=Contract(**p.model_dump());db.add(r);db.flush();refresh_contract_actions(db);db.commit();return {"id":r.id}

def _goal_row(r:FinancialGoal)->dict:
    remaining=max(Decimal("0"),r.target_amount-r.current_amount)
    months_left=None;monthly_required=None
    if r.target_date:
        today=date.today()
        months_left=max(1,(r.target_date.year-today.year)*12+r.target_date.month-today.month+(1 if r.target_date.day>today.day else 0))
        monthly_required=(remaining/Decimal(months_left)).quantize(Decimal("0.01"))
    planned=r.planned_monthly_contribution or Decimal("0")
    projected_months=None
    if remaining==0:projected_months=0
    elif planned>0:projected_months=int((remaining/planned).to_integral_value(rounding=ROUND_CEILING))
    return {"id":r.id,"type":r.goal_type,"name":r.name,"target_amount":str(r.target_amount),"current_amount":str(r.current_amount),"target_date":r.target_date,"priority":r.priority,"status":r.status,"planned_monthly_contribution":str(planned),"remaining_amount":str(remaining),"months_left":months_left,"monthly_required":None if monthly_required is None else str(monthly_required),"projected_months":projected_months}

@router.get("/goals")
def goals(db:Session=Depends(dbdep)):return [_goal_row(r) for r in db.scalars(select(FinancialGoal).order_by(FinancialGoal.created_at.desc())).all()]
@router.post("/goals")
def add_goal(p:GoalCreate,db:Session=Depends(dbdep)):
    r=FinancialGoal(**p.model_dump());db.add(r);db.commit();return _goal_row(r)
@router.patch("/goals/{goal_id}")
def progress(goal_id:str,p:GoalProgressUpdate,db:Session=Depends(dbdep)):
    r=db.get(FinancialGoal,goal_id)
    if not r:raise HTTPException(404,"Goal not found")
    r.current_amount=p.current_amount
    if p.planned_monthly_contribution is not None:r.planned_monthly_contribution=p.planned_monthly_contribution
    r.status="completed" if r.current_amount>=r.target_amount else "active"
    db.commit();return _goal_row(r)

@router.get("/portfolios")
def portfolios(db:Session=Depends(dbdep)):return [{"id":p.id,"name":p.name,"base_currency":p.base_currency,**portfolio_summary(db,p.id)} for p in db.scalars(select(Portfolio)).all()]
@router.post("/portfolios")
def add_portfolio(p:PortfolioCreate,db:Session=Depends(dbdep)):r=Portfolio(**p.model_dump());db.add(r);db.commit();return {"id":r.id}
@router.get("/securities")
def securities(db:Session=Depends(dbdep)):return [{"id":s.id,"name":s.name,"symbol":s.symbol,"isin":s.isin,"asset_class":s.asset_class,"currency":s.currency} for s in db.scalars(select(Security)).all()]
@router.post("/securities")
def add_security(p:SecurityCreate,db:Session=Depends(dbdep)):r=Security(**p.model_dump());db.add(r);db.commit();return {"id":r.id}
@router.post("/trades")
def trade(p:TradeCreate,db:Session=Depends(dbdep)):
    if not db.get(Portfolio,p.portfolio_id) or not db.get(Security,p.security_id):raise HTTPException(404,"Portfolio or security not found")
    r=Trade(**p.model_dump(),source_type="manual");db.add(r);db.flush()
    try:result=apply_trade(db,r)
    except ValueError as e:db.rollback();raise HTTPException(409,str(e))
    db.commit();return {"id":r.id,**{k:str(v) for k,v in result.items()}}

@router.get("/portfolios/{portfolio_id}/corporate-actions")
def corporate_actions(portfolio_id:str,db:Session=Depends(dbdep)):
    if not db.get(Portfolio,portfolio_id):raise HTTPException(404,"Portfolio not found")
    return list_actions(db,portfolio_id)

@router.post("/portfolios/{portfolio_id}/corporate-actions")
def corporate_action_add(portfolio_id:str,p:CorporateActionCreate,db:Session=Depends(dbdep)):
    if p.portfolio_id!=portfolio_id:raise HTTPException(400,"portfolio_id mismatch")
    if not db.get(Portfolio,portfolio_id) or not db.get(Security,p.security_id):raise HTTPException(404,"Portfolio or security not found")
    try:
        row=add_action(db,portfolio_id,p.security_id,p.action_type,p.effective_date,p.value,p.currency,p.notes)
        db.commit()
        return {"id":row.id,"applied":row.applied}
    except ValueError as exc:
        db.rollback();raise HTTPException(400,str(exc))

@router.post("/portfolios/{portfolio_id}/imports/broker")
async def broker_import(portfolio_id:str,file:UploadFile=File(...),db:Session=Depends(dbdep)):
    if not db.get(Portfolio,portfolio_id):raise HTTPException(404,"Portfolio not found")
    content=await file.read()
    if len(content)>10*1024*1024:raise HTTPException(413,"Broker file too large")
    try:
        result=import_broker_csv(db,portfolio_id,content,file.filename or "broker.csv")
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400,str(exc))

@router.get("/insurance/verdict")
def insurance_verdict_view(db:Session=Depends(dbdep)):
    result=insurance_verdict(db,use_ai=False);db.commit();return result

@router.post("/insurance/verdict/analyze")
def insurance_verdict_with_ai(db:Session=Depends(dbdep)):
    result=insurance_verdict(db,use_ai=True);db.commit();return result

@router.post("/insurance")
def add_insurance(p:InsuranceCreate,db:Session=Depends(dbdep)):r=InsurancePolicy(**p.model_dump(),insured_object_json="{}");db.add(r);db.commit();return {"id":r.id}
@router.get("/insurance")
def insurance(db:Session=Depends(dbdep)):
    sources=_document_sources_multi(db,"insurance_policy")
    return [{"id":r.id,"insurance_type":r.insurance_type,"annual_premium":str(r.annual_premium),"deductible":None if r.deductible is None else str(r.deductible),"contract_id":r.contract_id,"source_document_id":(sources.get(r.id) or [None])[0],"source_document_ids":sources.get(r.id,[]),"document_count":len(sources.get(r.id,[]))} for r in db.scalars(select(InsurancePolicy)).all()]
@router.post("/coverage")
def add_coverage(p:CoverageCreate,db:Session=Depends(dbdep)):r=CoverageFact(**p.model_dump(),conditions_json="{}",exclusions_json="{}");db.add(r);db.commit();return {"id":r.id}
@router.post("/coverage/compare")
def coverage_compare(p:CoverageCompareRequest,db:Session=Depends(dbdep)):
    try:return compare_coverages(db,p.left_id,p.right_id)
    except ValueError as e:raise HTTPException(404,str(e))

@router.post("/stress")
def stress(p:StressRequest,db:Session=Depends(dbdep)):
    wealth=wealth_summary(db);today=date.today();month_start=today.replace(day=1)
    flow=cash_flow(db,month_start,today)
    return run_stress(Decimal(wealth["accounts"]),flow["income"],flow["expenses"],Decimal(wealth["investments"]),p.income_reduction_pct,p.extraordinary_expense,p.portfolio_drop_pct,p.months)

@router.post("/rag/search")
def rag(p:RagSearchRequest,db:Session=Depends(dbdep)):return {"results":search(db,p.query,p.limit)}
@router.post("/rag/rebuild/{document_id}")
def rebuild(document_id:str,db:Session=Depends(dbdep)):
    from .models import Document
    d=db.get(Document,document_id)
    if not d:raise HTTPException(404,"Document not found")
    n=index_document_chunks(db,d);db.commit();return {"chunks":n}
@router.post("/chat")
def chat(p:ChatRequest,db:Session=Depends(dbdep)):return answer(db,p.question)

@router.post("/backups")
def backup(p:BackupCreate,db:Session=Depends(dbdep)):
    try:result=create_backup(p.passphrase,p.destination)
    except (ValueError,OSError) as e:raise HTTPException(400,str(e))
    r=BackupRecord(file_path=result["path"],sha256=result["sha256"]);db.add(r);db.commit();return result
@router.post("/backups/restore")
def restore(p:BackupRestore):
    try:return stage_restore(p.passphrase,p.path)
    except Exception as e:raise HTTPException(400,"Backup could not be verified or decrypted")

@router.get("/repair")
def repair_list(db:Session=Depends(dbdep)):rows=scan(db);db.commit();return [{"id":r.id,"issue_type":r.issue_type,"severity":r.severity,"repair_action":r.repair_action,"entity_type":r.entity_type,"entity_id":r.entity_id} for r in rows]
@router.post("/repair/{issue_id}")
def repair_run(issue_id:str,db:Session=Depends(dbdep)):
    try:result=repair(db,issue_id)
    except ValueError as e:raise HTTPException(400,str(e))
    db.commit();return result

@router.get("/tax/profile")
def tax_profile(jurisdiction:str="ES",tax_year:int=date.today().year,db:Session=Depends(dbdep)):
    return profile_dict(get_profile(db,jurisdiction.upper(),tax_year),jurisdiction.upper(),tax_year)

@router.put("/tax/profile")
@router.post("/tax/profile",include_in_schema=False)
def save_tax_profile(p:TaxProfileUpdate,db:Session=Depends(dbdep)):
    if p.children_under_three>p.dependent_children:
        raise HTTPException(400,"Los menores de tres años no pueden superar el número total de descendientes.")
    row=upsert_profile(db,p.model_dump());db.commit()
    return profile_dict(row,row.jurisdiction,row.tax_year)

@router.post("/tax/estimate")
def tax(p:TaxEstimateRequest,db:Session=Depends(dbdep)):
    return estimate(db,p.jurisdiction,p.tax_year)

@router.get("/tax/estimate",include_in_schema=False)
def tax_compat_get(jurisdiction:str="ES",tax_year:int=date.today().year,db:Session=Depends(dbdep)):
    return estimate(db,jurisdiction,tax_year)
@router.get("/market/quote/{symbol}")
def quote(symbol:str):
    try:return quote_with_free_fallback(symbol)
    except Exception as e:raise HTTPException(503,str(e))
@router.get("/news/search")
def news(q:str):
    if len(q)<2:raise HTTPException(400,"Query too short")
    try:return {"items":GdeltNewsProvider().search(q)}
    except Exception as e:raise HTTPException(503,str(e))
@router.post("/imports/statement")
async def statement(account_id:str,file:UploadFile=File(...),db:Session=Depends(dbdep)):
    if not db.get(Account,account_id):raise HTTPException(404,"Account not found")
    content=await file.read()
    if len(content)>30*1024*1024:raise HTTPException(413,"File too large")
    try:r=import_statement(db,account_id,file.filename or "statement",content)
    except ValueError as e:raise HTTPException(400,str(e))
    transfer_pairs=detect_internal_transfers(db)
    refunds=detect_refunds(db)
    db.commit()
    return {**r.__dict__,"transfer_pairs":transfer_pairs,"refunds":refunds}

@router.get("/coverage")
def coverage_list(db:Session=Depends(dbdep)):
    return [{"id":r.id,"coverage_type":r.coverage_type,"contract_id":r.contract_id,"insurance_policy_id":r.insurance_policy_id,"limit_amount":None if r.limit_amount is None else str(r.limit_amount),"deductible":None if r.deductible is None else str(r.deductible),"confidence":str(r.confidence),"user_verified":r.user_verified} for r in db.scalars(select(CoverageFact)).all()]

@router.post("/coverage/overlaps/scan")
def coverage_overlap_scan(db:Session=Depends(dbdep)):
    rows=scan_coverage_overlaps(db);db.commit()
    return {"overlaps":[{"id":r.id,"coverage_type":r.coverage_type,"left_id":r.left_coverage_fact_id,"right_id":r.right_coverage_fact_id,"overlap_type":r.overlap_type,"confidence":str(r.confidence)} for r in rows]}

@router.get("/coverage/overlaps")
def coverage_overlaps(db:Session=Depends(dbdep)):
    from .models_extended import CoverageOverlap
    rows=db.scalars(select(CoverageOverlap).order_by(CoverageOverlap.created_at.desc())).all()
    return [{"id":r.id,"coverage_type":r.coverage_type,"left_id":r.left_coverage_fact_id,"right_id":r.right_coverage_fact_id,"overlap_type":r.overlap_type,"confidence":str(r.confidence),"status":r.status} for r in rows]
