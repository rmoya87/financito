from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class AssetCreate(BaseModel):
    asset_type:str; name:str; current_value:Decimal; currency:str="EUR"; valuation_date:date; valuation_source:str="manual"; ownership_type:str="personal"; ownership_percentage:Decimal=Decimal("100")
class LiabilityCreate(BaseModel):
    liability_type:str; name:str; outstanding_amount:Decimal; currency:str="EUR"; annual_rate:Decimal|None=None; ownership_percentage:Decimal=Decimal("100")
class ContractCreate(BaseModel):
    provider_name:str; contract_type:str; start_date:date|None=None; renewal_date:date|None=None; cancellation_notice_days:int|None=None; permanence_end_date:date|None=None; early_exit_penalty:Decimal|None=None; annual_cost:Decimal|None=None; currency:str="EUR"; evidence_status:str="needs_more_data"
class GoalCreate(BaseModel):
    goal_type:str; name:str; target_amount:Decimal; current_amount:Decimal=Decimal("0"); target_date:date|None=None; priority:str="medium"; planned_monthly_contribution:Decimal=Decimal("0")
class PortfolioCreate(BaseModel):
    name:str; base_currency:str="EUR"
class SecurityCreate(BaseModel):
    asset_class:str; name:str; symbol:str|None=None; isin:str|None=None; currency:str="EUR"
class TradeCreate(BaseModel):
    portfolio_id:str; security_id:str; side:str=Field(pattern="^(buy|sell)$"); quantity:Decimal=Field(gt=0); price:Decimal=Field(gt=0); fees:Decimal=Decimal("0"); currency:str="EUR"; fx_rate:Decimal=Decimal("1"); executed_at:datetime
class InsuranceCreate(BaseModel):
    insurance_type:str; annual_premium:Decimal; contract_id:str|None=None; deductible:Decimal|None=None; currency:str="EUR"; policy_number_masked:str|None=None
class CoverageCreate(BaseModel):
    coverage_type:str; contract_id:str|None=None; insurance_policy_id:str|None=None; limit_amount:Decimal|None=None; deductible:Decimal|None=None; effective_from:date|None=None; effective_to:date|None=None; confidence:Decimal=Decimal("1"); user_verified:bool=True
class GoalProgressUpdate(BaseModel):
    current_amount:Decimal
class StressRequest(BaseModel):
    income_reduction_pct:Decimal=Decimal("0"); extraordinary_expense:Decimal=Decimal("0"); portfolio_drop_pct:Decimal=Decimal("0"); months:int=Field(default=6,ge=1,le=60)
class RagSearchRequest(BaseModel):
    query:str=Field(min_length=2,max_length=1000); limit:int=Field(default=8,ge=1,le=30)
class ChatRequest(BaseModel):
    question:str=Field(min_length=2,max_length=4000)
class BackupCreate(BaseModel):
    passphrase:str=Field(min_length=12,max_length=256); destination:str
class BackupRestore(BaseModel):
    passphrase:str=Field(min_length=12,max_length=256); path:str
class TaxEstimateRequest(BaseModel):
    jurisdiction:str="ES"; tax_year:int; assumed_rate:Decimal|None=None
class CostCenterCreate(BaseModel):
    name:str; center_type:str; metadata:dict={}
class CoverageCompareRequest(BaseModel):
    left_id:str; right_id:str


class CorporateActionCreate(BaseModel):
    portfolio_id:str
    security_id:str
    action_type:str=Field(pattern="^(dividend|split)$")
    effective_date:date
    value:Decimal=Field(gt=0)
    currency:str="EUR"
    notes:str|None=None


class MortgageProfileCreate(BaseModel):
    lender:str
    remaining_principal:Decimal=Field(gt=0)
    currency:str="EUR"
    interest_type:str=Field(pattern="^(fixed|variable|mixed)$")
    nominal_rate:Decimal=Field(ge=0,le=1)
    monthly_payment:Decimal=Field(gt=0)
    remaining_months:int=Field(gt=0,le=1200)
    early_repayment_fee:Decimal|None=Field(default=None,ge=0)

class MortgageProfileUpdate(MortgageProfileCreate):
    pass

class StoredMortgageScenarioRequest(BaseModel):
    mortgage_id:str

class StoredMortgagePrepaymentRequest(BaseModel):
    mortgage_id:str
    extra_payment:Decimal=Field(gt=0)

class StoredMortgageRatePathRequest(BaseModel):
    mortgage_id:str
    rate_steps:list[dict]=Field(default_factory=list,max_length=50)

class TrackedAssetCreate(BaseModel):
    asset_class:str=Field(pattern="^(stock|etf|fund|bond|crypto|cash)$")
    name:str
    identifier:str
    owned:bool=False
    portfolio_id:str|None=None
    quantity:Decimal|None=Field(default=None,gt=0)
    purchase_price:Decimal|None=Field(default=None,gt=0)
    purchase_date:date|None=None
    fees:Decimal=Field(default=Decimal("0"),ge=0)
    currency:str="EUR"
    provider_asset_id:str|None=None
    notes:str|None=None
