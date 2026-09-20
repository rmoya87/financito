from __future__ import annotations
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Account,Contract,FinancialGoal,Portfolio,Security,Position
from .models_extended import Asset,BackupRecord,CoverageFact,InsurancePolicy,Liability,RepairIssue,Trade
from .schemas_extended import AssetCreate,BackupCreate,BackupRestore,ChatRequest,ContractCreate,CoverageCompareRequest,CoverageCreate,GoalCreate,GoalProgressUpdate,InsuranceCreate,LiabilityCreate,PortfolioCreate,RagSearchRequest,SecurityCreate,StressRequest,TaxEstimateRequest,TradeCreate
from .domain.portfolio import apply_trade,portfolio_summary
from .domain.stress import run_stress
from .services.backup import create_backup,stage_restore
from .services.chat import answer
from .services.contracts import compare_coverages,refresh_contract_actions
from .services.import_formats import import_statement
from .services.rag import index_document_chunks,search
from .services.repair import repair,scan
from .services.tax import estimate
from .services.wealth import summary as wealth_summary
from .providers.market import AlphaVantageProvider
from .providers.enable_banking import EnableBankingProvider
from .providers.news import GdeltNewsProvider
router=APIRouter(prefix="/api/v1")

def dbdep():
    db=SessionLocal()
    try:yield db
    finally:db.close()

@router.get("/wealth")
def wealth(db:Session=Depends(dbdep)):return wealth_summary(db)
@router.get("/assets")
def assets(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.asset_type,"name":r.name,"value":str(r.current_value),"currency":r.currency,"valuation_date":r.valuation_date} for r in db.scalars(select(Asset).order_by(Asset.name)).all()]
@router.post("/assets")
def add_asset(p:AssetCreate,db:Session=Depends(dbdep)):r=Asset(**p.model_dump());db.add(r);db.commit();return {"id":r.id}
@router.get("/liabilities")
def liabilities(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.liability_type,"name":r.name,"amount":str(r.outstanding_amount),"currency":r.currency} for r in db.scalars(select(Liability).order_by(Liability.name)).all()]
@router.post("/liabilities")
def add_liability(p:LiabilityCreate,db:Session=Depends(dbdep)):r=Liability(**p.model_dump());db.add(r);db.commit();return {"id":r.id}

@router.get("/contracts")
def contracts(db:Session=Depends(dbdep)):refresh_contract_actions(db);db.commit();return [{"id":r.id,"provider_name":r.provider_name,"contract_type":r.contract_type,"renewal_date":r.renewal_date,"cancellation_notice_days":r.cancellation_notice_days,"early_exit_penalty":None if r.early_exit_penalty is None else str(r.early_exit_penalty),"annual_cost":None if r.annual_cost is None else str(r.annual_cost),"evidence_status":r.evidence_status} for r in db.scalars(select(Contract).order_by(Contract.provider_name)).all()]
@router.post("/contracts")
def add_contract(p:ContractCreate,db:Session=Depends(dbdep)):r=Contract(**p.model_dump());db.add(r);db.flush();refresh_contract_actions(db);db.commit();return {"id":r.id}

@router.get("/goals")
def goals(db:Session=Depends(dbdep)):return [{"id":r.id,"type":r.goal_type,"name":r.name,"target_amount":str(r.target_amount),"current_amount":str(r.current_amount),"target_date":r.target_date,"priority":r.priority,"status":r.status} for r in db.scalars(select(FinancialGoal)).all()]
@router.post("/goals")
def add_goal(p:GoalCreate,db:Session=Depends(dbdep)):r=FinancialGoal(**p.model_dump());db.add(r);db.commit();return {"id":r.id}
@router.patch("/goals/{goal_id}")
def progress(goal_id:str,p:GoalProgressUpdate,db:Session=Depends(dbdep)):
    r=db.get(FinancialGoal,goal_id)
    if not r:raise HTTPException(404,"Goal not found")
    r.current_amount=p.current_amount
    if r.current_amount>=r.target_amount:r.status="completed"
    db.commit();return {"id":r.id,"status":r.status}

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

@router.post("/insurance")
def add_insurance(p:InsuranceCreate,db:Session=Depends(dbdep)):r=InsurancePolicy(**p.model_dump(),insured_object_json="{}");db.add(r);db.commit();return {"id":r.id}
@router.get("/insurance")
def insurance(db:Session=Depends(dbdep)):return [{"id":r.id,"insurance_type":r.insurance_type,"annual_premium":str(r.annual_premium),"deductible":None if r.deductible is None else str(r.deductible),"contract_id":r.contract_id} for r in db.scalars(select(InsurancePolicy)).all()]
@router.post("/coverage")
def add_coverage(p:CoverageCreate,db:Session=Depends(dbdep)):r=CoverageFact(**p.model_dump(),conditions_json="{}",exclusions_json="{}");db.add(r);db.commit();return {"id":r.id}
@router.post("/coverage/compare")
def coverage_compare(p:CoverageCompareRequest,db:Session=Depends(dbdep)):
    try:return compare_coverages(db,p.left_id,p.right_id)
    except ValueError as e:raise HTTPException(404,str(e))

@router.post("/stress")
def stress(p:StressRequest,db:Session=Depends(dbdep)):
    wealth=wealth_summary(db);today=date.today();month_start=today.replace(day=1)
    from .models import Transaction
    tx=db.scalars(select(Transaction).where(Transaction.booking_date>=month_start,Transaction.booking_date<=today)).all()
    income=sum((t.amount for t in tx if t.amount>0 and not t.is_internal_transfer),Decimal("0"));expenses=sum((-t.amount for t in tx if t.amount<0 and not t.is_internal_transfer),Decimal("0"))
    return run_stress(Decimal(wealth["accounts"]),income,expenses,Decimal(wealth["investments"]),p.income_reduction_pct,p.extraordinary_expense,p.portfolio_drop_pct,p.months)

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

@router.post("/tax/estimate")
def tax(p:TaxEstimateRequest,db:Session=Depends(dbdep)):return estimate(db,p.jurisdiction,p.tax_year,p.assumed_rate)
@router.get("/market/quote/{symbol}")
def quote(symbol:str):
    try:return AlphaVantageProvider().quote(symbol)
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
    db.commit();return r.__dict__

@router.get("/coverage")
def coverage_list(db:Session=Depends(dbdep)):
    return [{"id":r.id,"coverage_type":r.coverage_type,"contract_id":r.contract_id,"insurance_policy_id":r.insurance_policy_id,"limit_amount":None if r.limit_amount is None else str(r.limit_amount),"deductible":None if r.deductible is None else str(r.deductible),"confidence":str(r.confidence),"user_verified":r.user_verified} for r in db.scalars(select(CoverageFact)).all()]

@router.get("/banking/aspsps")
def banking_aspsps(country:str="ES"):
    try:return EnableBankingProvider().aspsps(country)
    except Exception as e:raise HTTPException(503,str(e))

@router.post("/banking/auth")
def banking_auth(bank_name:str,country:str,redirect_url:str,state:str,valid_until:str,psu_type:str="personal"):
    try:return EnableBankingProvider().start_authorization(bank_name,country,redirect_url,state,valid_until,psu_type)
    except Exception as e:raise HTTPException(503,str(e))

@router.post("/banking/session")
def banking_session(code:str):
    try:return EnableBankingProvider().authorize_session(code)
    except Exception as e:raise HTTPException(503,str(e))

@router.get("/banking/session/{session_id}")
def banking_get_session(session_id:str):
    try:return EnableBankingProvider().session(session_id)
    except Exception as e:raise HTTPException(503,str(e))

@router.get("/banking/account/{account_id}/balances")
def banking_balances(account_id:str):
    try:return EnableBankingProvider().balances(account_id)
    except Exception as e:raise HTTPException(503,str(e))

@router.get("/banking/account/{account_id}/transactions")
def banking_transactions(account_id:str,date_from:str|None=None,date_to:str|None=None,continuation_key:str|None=None):
    try:return EnableBankingProvider().transactions(account_id,date_from,date_to,continuation_key)
    except Exception as e:raise HTTPException(503,str(e))
