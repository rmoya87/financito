from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    institution_name: str = Field(default="Manual", max_length=120)
    account_type: str = "checking"
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    iban_masked: str | None = None
    current_balance: Decimal = Decimal("0")
    available_balance: Decimal | None = None


class AccountOut(ORMModel):
    id: str
    name: str
    institution_name: str
    account_type: str
    currency: str
    current_balance: Decimal
    available_balance: Decimal | None
    sync_status: str


class TransactionOut(ORMModel):
    id: str
    account_id: str
    booking_date: date
    amount: Decimal
    currency: str
    description_raw: str
    merchant_raw: str | None
    category_id: str | None
    categorization_method: str
    categorization_confidence: Decimal
    user_verified: bool
    is_internal_transfer: bool


class TransactionCategoryUpdate(BaseModel):
    category_id: str


class CommitmentCreate(BaseModel):
    commitment_type: str
    title: str
    amount: Decimal
    currency: str = "EUR"
    due_date: date
    recurrence: str | None = None
    confidence: Decimal = Decimal("1")
    mandatory: bool = True
    cancellable: bool = False


class BudgetCreate(BaseModel):
    category_id: str
    amount: Decimal
    currency: str = "EUR"
    period_type: str = "monthly"
    alert_threshold: Decimal = Decimal("0.8")


class DocumentIndexRequest(BaseModel):
    path: str
    document_type: str = "unknown"


class DocumentMortgageLinkUpdate(BaseModel):
    mortgage_id: str | None = None


class DocumentEntityLinkUpdate(BaseModel):
    entity_type: str = Field(pattern="^(insurance_policy|contract|mortgage)$")
    entity_id: str | None = None


class FactUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|inferred|not_found|ambiguous|conflicting|superseded)$")
    user_verified: bool = True

class ManualFactCreate(BaseModel):
    fact_type:str=Field(pattern="^(contract_term|mortgage_term|linked_product|coverage_fact|investment_term)$")
    key:str=Field(min_length=1,max_length=100)
    value:str=Field(min_length=1,max_length=4000)
    unit:str|None=Field(default=None,max_length=40)
    coverage_type:str|None=Field(default=None,max_length=100)
    limit_amount:str|None=Field(default=None,max_length=80)
    deductible:str|None=Field(default=None,max_length=80)
    conditions:str|None=Field(default=None,max_length=2000)
    exclusions:str|None=Field(default=None,max_length=2000)
    source_page:int|None=Field(default=None,ge=1)


class ActionUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|done|dismissed|snoozed)$")
    notes: str | None = None


class ForecastRequest(BaseModel):
    start: date
    end: date


class MortgageScenarioRequest(BaseModel):
    principal: Decimal
    annual_rate: Decimal = Field(description="Nominal annual rate as decimal, e.g. 0.025")
    months: int = Field(gt=0, le=600)


class OptimizationRequest(BaseModel):
    gross_annual_saving: Decimal
    switching_costs: Decimal = Decimal("0")
    penalties: Decimal | None = None
    lost_benefits: Decimal = Decimal("0")
    additional_recurring_costs: Decimal = Decimal("0")
    tax_impact: Decimal = Decimal("0")


class MortgagePrepaymentRequest(BaseModel):
    principal: Decimal = Field(gt=0)
    annual_rate: Decimal = Field(ge=0, le=1)
    months: int = Field(gt=0, le=1200)
    extra_payment: Decimal = Field(ge=0)
    prepayment_fee: Decimal = Field(default=Decimal("0"), ge=0)


class MortgageRateStep(BaseModel):
    month:int=Field(ge=1,le=1200)
    annual_rate:Decimal=Field(ge=0,le=1)

class MortgageRatePathRequest(BaseModel):
    principal:Decimal=Field(gt=0)
    months:int=Field(gt=0,le=1200)
    initial_annual_rate:Decimal=Field(ge=0,le=1)
    rate_steps:list[MortgageRateStep]=Field(default_factory=list,max_length=50)
