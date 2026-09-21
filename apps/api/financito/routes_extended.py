from __future__ import annotations
from datetime import date
from decimal import Decimal,ROUND_CEILING
import json
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Account,Contract,ExtractedFact,FinancialGoal,Mortgage,Portfolio,Security
from .models_extended import Asset,BackupRecord,CoverageFact,InsurancePolicy,Liability,MortgageProfileExtra,RepairIssue,Trade,TrackedAsset
from .models_analytics import EntityLink,EntitySnapshot,LinkedProduct
from .schemas_extended import AssetCreate,AssetSimulationStart,BackupCreate,BackupRestore,ChatRequest,ContractCreate,CoverageCompareRequest,CoverageCreate,CorporateActionCreate,GoalCreate,GoalProgressUpdate,InsuranceCreate,InsuranceUpdate,LiabilityCreate,MortgageExtraUpdate,MortgageProfileCreate,MortgageProfileUpdate,PortfolioCreate,RagSearchRequest,SecurityCreate,StoredMortgagePrepaymentRequest,StoredMortgageRatePathRequest,StoredMortgageScenarioRequest,StressRequest,TaxEstimateRequest,TaxProfileUpdate,TrackedAssetCreate,TradeCreate
from .domain.portfolio import apply_trade,portfolio_summary
from .domain.engines import MortgageEngine,MortgagePrepaymentEngine,MortgageRatePathEngine
from .domain.stress import run_stress
from .domain.analytics import detect_recurring
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
from .services.contractual_costs import mortgage_contract_context,resolve_prepayment_penalty,switching_readiness
from .services.market_research import scan_public_market
from .services.mortgage_cost import current_remaining_apr_estimate,due_rate_review_estimate,rate_review_readiness
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
def decision_lab_market_scan(mortgage_id:str|None=None,db:Session=Depends(dbdep)):
    if mortgage_id and not db.get(Mortgage,mortgage_id):
        raise HTTPException(404,"Mortgage not found")
    return scan_public_market(db,mortgage_id)

@router.get("/decision-lab/switching-readiness")
def decision_lab_switching_readiness(mortgage_id:str|None=None,db:Session=Depends(dbdep)):
    return switching_readiness(db,mortgage_id)

@router.get("/decision-lab/context")
def decision_lab_context(db:Session=Depends(dbdep)):
    return live_decision_context(db)

@router.get("/mortgages")
def mortgages(db:Session=Depends(dbdep)):
    sources_multi=_document_sources_multi(db,"mortgage")
    rows=[]
    for r in db.scalars(select(Mortgage).order_by(Mortgage.updated_at.desc())).all():
        document_ids=sources_multi.get(r.id,[])
        rows.append({
            **mortgage_row(r),
            "source_document_id":document_ids[0] if document_ids else None,
            "source_document_ids":document_ids,
            "document_count":len(document_ids),
        })
    return rows

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

@router.delete("/mortgages/{mortgage_id}")
def delete_mortgage(mortgage_id:str,db:Session=Depends(dbdep)):
    row=db.get(Mortgage,mortgage_id)
    if not row:raise HTTPException(404,"Mortgage not found")
    for link in db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
        EntityLink.to_type=="mortgage",
        EntityLink.to_id==mortgage_id,
    )).all():
        db.delete(link)
    extra=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage_id))
    if extra is not None:db.delete(extra)
    record_snapshot(db,"mortgage",row.id,{
        "remaining_principal":str(row.remaining_principal),
        "nominal_rate":str(row.nominal_rate),
        "monthly_payment":str(row.monthly_payment),
        "remaining_months":row.remaining_months,
        "deleted":True,
        "currency":row.currency,
    },source="mortgage_deleted")
    db.delete(row);db.commit()
    return {"id":mortgage_id,"deleted":True}


def _mortgage_extra_payload(row:MortgageProfileExtra|None)->dict:
    if row is None:
        return {
            "original_principal":None,"original_term_months":None,"start_date":None,"maturity_date":None,
            "apr_rate":None,"reference_index":None,"differential_rate":None,"rate_review_months":None,
            "next_review_date":None,"opening_fee_percent":None,"early_repayment_fee_percent":None,
            "subrogation_fee_percent":None,"cancellation_fee_percent":None,"notes":None,
        }
    return {
        "original_principal":None if row.original_principal is None else str(row.original_principal),
        "original_term_months":row.original_term_months,
        "start_date":row.start_date,
        "maturity_date":row.maturity_date,
        "apr_rate":None if row.apr_rate is None else str(row.apr_rate),
        "reference_index":row.reference_index,
        "differential_rate":None if row.differential_rate is None else str(row.differential_rate),
        "rate_review_months":row.rate_review_months,
        "next_review_date":row.next_review_date,
        "opening_fee_percent":None if row.opening_fee_percent is None else str(row.opening_fee_percent),
        "early_repayment_fee_percent":None if row.early_repayment_fee_percent is None else str(row.early_repayment_fee_percent),
        "subrogation_fee_percent":None if row.subrogation_fee_percent is None else str(row.subrogation_fee_percent),
        "cancellation_fee_percent":None if row.cancellation_fee_percent is None else str(row.cancellation_fee_percent),
        "notes":row.notes,
    }

@router.get("/mortgages/{mortgage_id}/profile-extra")
def mortgage_profile_extra(mortgage_id:str,db:Session=Depends(dbdep)):
    if not db.get(Mortgage,mortgage_id):raise HTTPException(404,"Mortgage not found")
    row=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage_id))
    return _mortgage_extra_payload(row)

@router.patch("/mortgages/{mortgage_id}/profile-extra")
def update_mortgage_profile_extra(mortgage_id:str,p:MortgageExtraUpdate,db:Session=Depends(dbdep)):
    if not db.get(Mortgage,mortgage_id):raise HTTPException(404,"Mortgage not found")
    row=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage_id))
    if row is None:
        row=MortgageProfileExtra(mortgage_id=mortgage_id)
        db.add(row)
    for key,value in p.model_dump().items():
        setattr(row,key,value)
    db.commit()
    return _mortgage_extra_payload(row)

@router.get("/wealth/home")
def wealth_home(mortgage_id:str|None=None,db:Session=Depends(dbdep)):
    mortgage=db.get(Mortgage,mortgage_id) if mortgage_id else db.scalar(select(Mortgage).order_by(Mortgage.updated_at.desc()))
    if mortgage_id and mortgage is None:raise HTTPException(404,"Mortgage not found")
    properties=db.scalars(select(Asset).where(
        Asset.asset_type.in_(["property","home","house","real_estate"])
    ).order_by(Asset.valuation_date.desc(),Asset.current_value.desc())).all()
    home=properties[0] if properties else None
    contracts={row.id:row for row in db.scalars(select(Contract)).all()}
    linked_policy_ids=set()
    if mortgage is not None:
        linked_policy_ids=set(db.scalars(select(LinkedProduct.linked_product_id).where(
            LinkedProduct.parent_product_type=="mortgage",
            LinkedProduct.parent_product_id==mortgage.id,
            LinkedProduct.linked_product_type=="insurance_policy",
        )).all())
    policies=[]
    for policy in db.scalars(select(InsurancePolicy)).all():
        kind=(policy.insurance_type or "").lower()
        property_related=any(token in kind for token in ("home","house","hogar","mortgage","hipoteca"))
        explicitly_linked=policy.id in linked_policy_ids
        # Life insurance is only shown in Casa when evidence actually links it
        # to the selected mortgage. Home insurance remains property-relevant.
        if not property_related and not explicitly_linked:
            continue
        contract=contracts.get(policy.contract_id or "")
        policies.append({
            "id":policy.id,
            "insurance_type":policy.insurance_type,
            "annual_premium":str(policy.annual_premium),
            "provider":None if contract is None else contract.provider_name,
            "renewal_date":None if contract is None else contract.renewal_date,
            "linked_to_mortgage":explicitly_linked,
        })

    if mortgage is None:
        return {
            "property":None if home is None else {
                "id":home.id,"name":home.name,"value":str(home.current_value),"currency":home.currency,
                "valuation_date":home.valuation_date,"valuation_source":home.valuation_source,
                "ownership_percentage":str(home.ownership_percentage),
            },
            "mortgage":None,
            "extra":_mortgage_extra_payload(None),
            "document_facts":{},
            "source_documents":[],
            "insurance":policies,
            "equity":None,
            "owned_equity":None,
            "ltv":None,
            "pending_review":[],
            "current_apr_estimate":None,
            "rate_review_automation":{"status":"not_available","automatic":False,"missing":["mortgage"]},
            "missing":[
                {"key":"mortgage","label":"Datos de la hipoteca","reason":"Necesarios para calcular cuota, intereses y escenarios de mejora."}
            ],
        }

    extra=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage.id))
    context=mortgage_contract_context(db,mortgage.id)
    by_key=context["by_key"]
    pending_by_key=context.get("pending_by_key",{})
    extra_payload=_mortgage_extra_payload(extra)

    # Confirmed document evidence fills informational gaps without silently
    # overwriting manual profile values.
    evidence_map={
        "apr_rate":"apr_rate","reference_index":"reference_index","differential_rate":"differential_rate",
        "rate_review_months":"rate_review_months","next_review_date":"next_review_date","opening_fee_percent":"opening_fee_percent",
        "early_repayment_fee_percent":"early_repayment_fee_percent","subrogation_fee_percent":"subrogation_fee_percent",
        "cancellation_fee_percent":"cancellation_fee_percent",
    }
    for target,key in evidence_map.items():
        if extra_payload.get(target) is None and by_key.get(key):
            raw=by_key[key].get("value")
            if target in {"apr_rate","differential_rate"} and raw not in {None,""}:
                try:extra_payload[target]=str(Decimal(str(raw).replace(",","."))/Decimal("100"))
                except Exception:extra_payload[target]=raw
            elif target=="rate_review_months" and raw not in {None,""}:
                try:extra_payload[target]=int(Decimal(str(raw).replace(",",".")))
                except Exception:extra_payload[target]=raw
            else:
                extra_payload[target]=raw

    equity=None;ltv=None;owned_equity=None
    if home is not None:
        # LTV bancario se calcula contra el valor total de la garantía, no
        # contra el porcentaje patrimonial del usuario.
        equity=(home.current_value-mortgage.remaining_principal).quantize(Decimal("0.01"))
        if home.current_value>0:
            ltv=(mortgage.remaining_principal/home.current_value*Decimal("100")).quantize(Decimal("0.01"))
        owned_value=home.current_value*home.ownership_percentage/Decimal("100")
        owned_equity=(owned_value-mortgage.remaining_principal).quantize(Decimal("0.01"))

    missing=[]
    pending_review=[]
    def candidate_for(keys):
        for candidate_key in keys:
            candidate=pending_by_key.get(candidate_key)
            if candidate:
                return candidate
        return None
    def need(key,label,reason,value,alternatives=None):
        if value not in {None,""}:
            return
        candidate=candidate_for(alternatives or [key])
        if candidate:
            pending_review.append({
                "key":key,
                "label":label,
                "reason":"Financito ya ha localizado un valor en la documentación. Revísalo y confírmalo para que entre en cálculos.",
                "value":candidate.get("value"),
                "unit":candidate.get("unit"),
                "document_id":candidate.get("document_id"),
                "page":candidate.get("page"),
                "source":candidate.get("source"),
                "status":candidate.get("status"),
            })
        else:
            missing.append({"key":key,"label":label,"reason":reason})
    if home is None:
        missing.append({"key":"property_value","label":"Valor actual de la vivienda","reason":"Permite calcular patrimonio inmobiliario y LTV."})
    need("apr_rate","TAE actual","La IA local no ha encontrado todavía una TAE explícita suficiente para comparar el coste total.",extra_payload.get("apr_rate"))
    if mortgage.interest_type in {"variable","mixed"}:
        need("reference_index","Índice de referencia","La IA local no ha encontrado todavía un índice de referencia explícito.",extra_payload.get("reference_index"))
        need("differential_rate","Diferencial","La IA local no ha encontrado todavía un diferencial explícito.",extra_payload.get("differential_rate"))
        need("rate_review_months","Periodicidad de revisión","La IA local no ha encontrado todavía la periodicidad de revisión.",extra_payload.get("rate_review_months"))
        need("next_review_date","Próxima revisión","La IA local no ha encontrado todavía una próxima fecha de revisión explícita.",extra_payload.get("next_review_date"))
    if mortgage.early_repayment_fee is None and extra_payload.get("early_repayment_fee_percent") is None:
        need("early_repayment_fee_percent","Comisión de amortización anticipada","No consta todavía una comisión o fórmula verificable de amortización anticipada.",None,["early_repayment_fee_percent","early_exit_penalty"])
    if extra_payload.get("subrogation_fee_percent") is None and extra_payload.get("cancellation_fee_percent") is None:
        need("subrogation_fee_percent","Coste/comisión de subrogación o salida","No consta todavía un coste o fórmula verificable de salida/subrogación.",None,["subrogation_fee_percent","cancellation_fee_percent","early_exit_penalty"])

    return {
        "property":None if home is None else {
            "id":home.id,"name":home.name,"value":str(home.current_value),"currency":home.currency,
            "valuation_date":home.valuation_date,"valuation_source":home.valuation_source,
            "ownership_percentage":str(home.ownership_percentage),
        },
        "mortgage":mortgage_row(mortgage),
        "extra":extra_payload,
        "document_facts":by_key,
        "source_documents":context["source_documents"],
        "insurance":policies,
        "equity":None if equity is None else str(equity),
        "owned_equity":None if owned_equity is None else str(owned_equity),
        "ltv":None if ltv is None else str(ltv),
        "pending_review":pending_review,
        "current_apr_estimate":current_remaining_apr_estimate(db,mortgage),
        "rate_review_automation":due_rate_review_estimate(db,mortgage),
        "missing":missing,
    }


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

@router.get("/tracked-assets/history")
def tracked_assets_history(days:int=365,db:Session=Depends(dbdep)):
    from datetime import datetime,timedelta,timezone
    from .services.market_data import history
    days=max(7,min(days,1825))
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    result=[]
    for item in tracked_assets(db):
        rows=[]
        for row in history(db,item["security_id"]):
            stamp=row["timestamp"]
            if stamp.tzinfo is None:
                stamp=stamp.replace(tzinfo=timezone.utc)
            if stamp>=cutoff:
                rows.append(row)
        result.append({
            "security_id":item["security_id"],
            "name":item["name"],
            "identifier":item["identifier"],
            "currency":item["currency"],
            "owned":item["owned"],
            "rows":rows,
        })
    return result

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
def tracked_assets_refresh_all(include_history:bool=False,db:Session=Depends(dbdep)):
    from .services.market_data import refresh_history,refresh_security
    rows=tracked_assets(db)
    refreshed=[];failed=[]
    for item in rows:
        try:
            quote=refresh_security(db,item["security_id"])
            history_result=refresh_history(db,item["security_id"]) if include_history else None
            refreshed.append({"security_id":item["security_id"],"quote":quote,"history":history_result})
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
    assets=[]
    for row in db.scalars(select(Asset).order_by(Asset.asset_type,Asset.name)).all():
        snapshots=db.scalars(select(EntitySnapshot).where(
            EntitySnapshot.entity_type=="asset",
            EntitySnapshot.entity_id==row.id,
        ).order_by(EntitySnapshot.as_of_date.desc())).all()
        previous_value=None;previous_date=None
        for snapshot in snapshots:
            if snapshot.as_of_date>=row.valuation_date:
                continue
            try:
                values=json.loads(snapshot.values_json or "{}")
                candidate=Decimal(str(values.get("value")))
            except Exception:
                continue
            previous_value=candidate;previous_date=snapshot.as_of_date;break
        change_amount=None;change_pct=None
        if previous_value is not None:
            change_amount=(row.current_value-previous_value).quantize(Decimal("0.01"))
            if previous_value!=0:
                change_pct=(change_amount/previous_value*Decimal("100")).quantize(Decimal("0.01"))
        assets.append({
            "id":row.id,
            "type":row.asset_type,
            "name":row.name,
            "value":str(row.current_value),
            "currency":row.currency,
            "valuation_date":row.valuation_date,
            "valuation_source":row.valuation_source,
            "ownership_type":row.ownership_type,
            "ownership_percentage":str(row.ownership_percentage),
            "previous_value":None if previous_value is None else str(previous_value),
            "previous_valuation_date":previous_date,
            "change_amount":None if change_amount is None else str(change_amount),
            "change_pct":None if change_pct is None else str(change_pct),
        })
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
        "early_repayment_fee":None if row.early_repayment_fee is None else str(row.early_repayment_fee),
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
@router.patch("/assets/{asset_id}")
def update_asset(asset_id:str,p:AssetCreate,db:Session=Depends(dbdep)):
    r=db.get(Asset,asset_id)
    if not r:raise HTTPException(404,"Asset not found")
    for key,value in p.model_dump().items():setattr(r,key,value)
    db.flush()
    record_snapshot(db,"asset",r.id,{"value":str(r.current_value),"ownership_percentage":str(r.ownership_percentage),"currency":r.currency},r.valuation_date,"asset_updated")
    db.commit();return {"id":r.id}

@router.delete("/assets/{asset_id}")
def delete_asset(asset_id:str,db:Session=Depends(dbdep)):
    r=db.get(Asset,asset_id)
    if not r:raise HTTPException(404,"Asset not found")
    record_snapshot(db,"asset",r.id,{
        "value":str(r.current_value),
        "ownership_percentage":str(r.ownership_percentage),
        "currency":r.currency,
        "deleted":True,
    },r.valuation_date,"asset_deleted")
    db.delete(r);db.commit()
    return {"id":asset_id,"deleted":True}
@router.get("/liabilities")
def liabilities(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.liability_type,"name":r.name,"amount":str(r.outstanding_amount),"currency":r.currency} for r in db.scalars(select(Liability).order_by(Liability.name)).all()]
@router.post("/liabilities")
def add_liability(p:LiabilityCreate,db:Session=Depends(dbdep)):
    r=Liability(**p.model_dump());db.add(r);db.flush()
    record_snapshot(db,"liability",r.id,{"outstanding_amount":str(r.outstanding_amount),"ownership_percentage":str(r.ownership_percentage),"currency":r.currency},source="liability_created")
    db.commit();return {"id":r.id}

@router.delete("/liabilities/{liability_id}")
def delete_liability(liability_id:str,db:Session=Depends(dbdep)):
    row=db.get(Liability,liability_id)
    if not row:raise HTTPException(404,"Liability not found")
    record_snapshot(db,"liability",row.id,{
        "outstanding_amount":str(row.outstanding_amount),
        "ownership_percentage":str(row.ownership_percentage),
        "currency":row.currency,
        "deleted":True,
    },source="liability_deleted")
    db.delete(row);db.commit()
    return {"id":liability_id,"deleted":True}

@router.get("/contracts")
def contracts(db:Session=Depends(dbdep)):
    refresh_contract_actions(db);db.commit()
    sources=_document_sources_multi(db,"contract")
    rows=db.scalars(select(Contract).where(
        Contract.contract_type.notin_(["insurance","mortgage"])
    ).order_by(Contract.provider_name)).all()
    result=[]
    for r in rows:
        document_ids=sources.get(r.id,[])
        pending=[]
        if document_ids:
            facts=db.scalars(select(ExtractedFact).where(
                ExtractedFact.document_id.in_(document_ids),
                ExtractedFact.fact_type.in_(["contract_term","linked_product","investment_term"]),
                ExtractedFact.user_verified.is_(False),
                ExtractedFact.status.in_(["inferred","ambiguous","conflicting"]),
            ).order_by(ExtractedFact.updated_at.desc())).all()
            seen=set()
            for fact in facts:
                if fact.key in seen:continue
                seen.add(fact.key)
                try:
                    payload=json.loads(fact.value_json)
                    value=payload.get("value") if isinstance(payload,dict) else payload
                    unit=payload.get("unit") if isinstance(payload,dict) else None
                    source=payload.get("source") if isinstance(payload,dict) else None
                except Exception:
                    value=fact.value_json;unit=None;source=None
                pending.append({
                    "key":fact.key,"value":value,"unit":unit,"document_id":fact.document_id,
                    "page":fact.source_page,"status":fact.status,
                    "source":source or "deterministic_extractor",
                })
        result.append({
            "id":r.id,"provider_name":r.provider_name,"contract_type":r.contract_type,
            "renewal_date":r.renewal_date,"cancellation_notice_days":r.cancellation_notice_days,
            "early_exit_penalty":None if r.early_exit_penalty is None else str(r.early_exit_penalty),
            "annual_cost":None if r.annual_cost is None else str(r.annual_cost),
            "evidence_status":r.evidence_status,"source_document_id":(document_ids or [None])[0],
            "source_document_ids":document_ids,"document_count":len(document_ids),
            "pending_review":pending,
        })
    return result
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

def _insurance_row(db:Session,row:InsurancePolicy,sources:dict[str,list[str]]|None=None)->dict:
    sources=sources or _document_sources_multi(db,"insurance_policy")
    document_ids=sources.get(row.id,[])
    contract=db.get(Contract,row.contract_id) if row.contract_id else None
    return {
        "id":row.id,
        "insurance_type":row.insurance_type,
        "annual_premium":str(row.annual_premium),
        "deductible":None if row.deductible is None else str(row.deductible),
        "currency":row.currency,
        "policy_number_masked":row.policy_number_masked,
        "contract_id":row.contract_id,
        "provider_name":None if contract is None else contract.provider_name,
        "renewal_date":None if contract is None else contract.renewal_date,
        "cancellation_notice_days":None if contract is None else contract.cancellation_notice_days,
        "early_exit_penalty":None if contract is None or contract.early_exit_penalty is None else str(contract.early_exit_penalty),
        "evidence_status":None if contract is None else contract.evidence_status,
        "source_document_id":document_ids[0] if document_ids else None,
        "source_document_ids":document_ids,
        "document_count":len(document_ids),
    }

def _ensure_insurance_contract(db:Session,p:InsuranceCreate|InsuranceUpdate,current:InsurancePolicy|None=None)->Contract|None:
    contract=db.get(Contract,p.contract_id) if p.contract_id else (db.get(Contract,current.contract_id) if current is not None and current.contract_id else None)
    needs_contract=bool(p.provider_name or p.renewal_date or p.cancellation_notice_days is not None or p.early_exit_penalty is not None or contract)
    if not needs_contract:return contract
    if contract is None:
        contract=Contract(
            provider_name=(p.provider_name or "Aseguradora pendiente").strip()[:180],
            contract_type="insurance",
            currency=p.currency,
            evidence_status="manual",
        )
        db.add(contract);db.flush()
    if p.provider_name:contract.provider_name=p.provider_name.strip()[:180]
    contract.contract_type="insurance"
    contract.annual_cost=p.annual_premium
    contract.renewal_date=p.renewal_date
    contract.cancellation_notice_days=p.cancellation_notice_days
    contract.early_exit_penalty=p.early_exit_penalty
    if contract.evidence_status=="needs_more_data" and p.provider_name:
        contract.evidence_status="manual"
    return contract

@router.post("/insurance")
def add_insurance(p:InsuranceCreate,db:Session=Depends(dbdep)):
    contract=_ensure_insurance_contract(db,p)
    payload=p.model_dump(exclude={"provider_name","renewal_date","cancellation_notice_days","early_exit_penalty"})
    payload["contract_id"]=None if contract is None else contract.id
    row=InsurancePolicy(**payload,insured_object_json="{}")
    db.add(row);db.flush();db.commit()
    return _insurance_row(db,row)

@router.get("/insurance")
def insurance(db:Session=Depends(dbdep)):
    sources=_document_sources_multi(db,"insurance_policy")
    return [_insurance_row(db,r,sources) for r in db.scalars(select(InsurancePolicy).order_by(InsurancePolicy.updated_at.desc())).all()]

@router.patch("/insurance/{policy_id}")
def update_insurance(policy_id:str,p:InsuranceUpdate,db:Session=Depends(dbdep)):
    row=db.get(InsurancePolicy,policy_id)
    if not row:raise HTTPException(404,"Insurance policy not found")
    contract=_ensure_insurance_contract(db,p,row)
    row.insurance_type=p.insurance_type
    row.annual_premium=p.annual_premium
    row.deductible=p.deductible
    row.currency=p.currency
    row.policy_number_masked=p.policy_number_masked
    row.contract_id=None if contract is None else contract.id
    db.commit()
    return _insurance_row(db,row)

@router.delete("/insurance/{policy_id}")
def delete_insurance(policy_id:str,db:Session=Depends(dbdep)):
    row=db.get(InsurancePolicy,policy_id)
    if not row:raise HTTPException(404,"Insurance policy not found")
    contract_id=row.contract_id
    for link in db.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
        EntityLink.to_type=="insurance_policy",
        EntityLink.to_id==policy_id,
    )).all():
        db.delete(link)
    if contract_id:
        for link in db.scalars(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="contract",
            EntityLink.to_id==contract_id,
        )).all():
            db.delete(link)
    for coverage in db.scalars(select(CoverageFact).where(CoverageFact.insurance_policy_id==policy_id)).all():
        db.delete(coverage)
    for linked in db.scalars(select(LinkedProduct).where(
        LinkedProduct.linked_product_type=="insurance_policy",
        LinkedProduct.linked_product_id==policy_id,
    )).all():
        db.delete(linked)
    db.delete(row);db.flush()
    if contract_id:
        contract=db.get(Contract,contract_id)
        other=db.scalar(select(InsurancePolicy.id).where(InsurancePolicy.contract_id==contract_id))
        if contract is not None and other is None and contract.contract_type=="insurance":
            db.delete(contract)
    db.commit()
    return {"id":policy_id,"deleted":True}
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
    recurring_count=len(detect_recurring(db,use_ai=True))
    db.commit()
    return {**r.__dict__,"transfer_pairs":transfer_pairs,"refunds":refunds,"recurring_series":recurring_count}

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
