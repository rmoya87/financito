from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import TimestampMixin, uuid_str

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Asset(Base, TimestampMixin):
    __tablename__="asset"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    asset_type:Mapped[str]=mapped_column(String(60),index=True)
    name:Mapped[str]=mapped_column(String(180))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    current_value:Mapped[Decimal]=mapped_column(Numeric(18,4))
    valuation_date:Mapped[date]=mapped_column(Date)
    valuation_source:Mapped[str]=mapped_column(String(80),default="manual")
    ownership_type:Mapped[str]=mapped_column(String(30),default="personal")
    ownership_percentage:Mapped[Decimal]=mapped_column(Numeric(6,3),default=Decimal("100"))

class Liability(Base, TimestampMixin):
    __tablename__="liability"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    liability_type:Mapped[str]=mapped_column(String(60),index=True)
    name:Mapped[str]=mapped_column(String(180))
    outstanding_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    annual_rate:Mapped[Decimal|None]=mapped_column(Numeric(8,6),nullable=True)
    ownership_percentage:Mapped[Decimal]=mapped_column(Numeric(6,3),default=Decimal("100"))

class Trade(Base, TimestampMixin):
    __tablename__="trade"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    portfolio_id:Mapped[str]=mapped_column(ForeignKey("portfolio.id",ondelete="CASCADE"),index=True)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    side:Mapped[str]=mapped_column(String(10))
    quantity:Mapped[Decimal]=mapped_column(Numeric(24,10))
    price:Mapped[Decimal]=mapped_column(Numeric(18,8))
    fees:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    fx_rate:Mapped[Decimal]=mapped_column(Numeric(18,8),default=Decimal("1"))
    executed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    source_type:Mapped[str]=mapped_column(String(40),default="manual")
    source_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)


class TrackedAsset(Base, TimestampMixin):
    __tablename__="tracked_asset"
    __table_args__=(UniqueConstraint("security_id",name="uq_tracked_asset_security"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    tracking_state:Mapped[str]=mapped_column(String(20),default="watching")
    provider_asset_id:Mapped[str|None]=mapped_column(String(120),nullable=True,index=True)
    preferred_currency:Mapped[str]=mapped_column(String(3),default="EUR")
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)

class AssetSimulation(Base, TimestampMixin):
    __tablename__="asset_simulation"
    __table_args__=(UniqueConstraint("security_id",name="uq_asset_simulation_security"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)
    invested_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    entry_price:Mapped[Decimal]=mapped_column(Numeric(18,8))
    quantity:Mapped[Decimal]=mapped_column(Numeric(24,10))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class TaxProfile(Base, TimestampMixin):
    __tablename__="tax_profile"
    __table_args__=(UniqueConstraint("jurisdiction","tax_year",name="uq_tax_profile_year"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    jurisdiction:Mapped[str]=mapped_column(String(8),default="ES",index=True)
    tax_year:Mapped[int]=mapped_column(Integer,index=True)
    autonomous_community:Mapped[str|None]=mapped_column(String(80),nullable=True)
    filing_status:Mapped[str|None]=mapped_column(String(30),nullable=True)
    adults:Mapped[int]=mapped_column(Integer,default=1)
    dependent_children:Mapped[int]=mapped_column(Integer,default=0)
    children_under_three:Mapped[int]=mapped_column(Integer,default=0)
    primary_residence:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    employment_income:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    social_security_contributions:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    employment_deductible_expenses:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    tax_withholdings:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    interest_income:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    other_general_income:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    carried_forward_savings_losses:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    pension_contributions:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))

class TaxLot(Base):
    __tablename__="tax_lot"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    portfolio_id:Mapped[str]=mapped_column(ForeignKey("portfolio.id",ondelete="CASCADE"),index=True)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    acquisition_date:Mapped[date]=mapped_column(Date,index=True)
    quantity_original:Mapped[Decimal]=mapped_column(Numeric(24,10))
    quantity_remaining:Mapped[Decimal]=mapped_column(Numeric(24,10))
    unit_cost:Mapped[Decimal]=mapped_column(Numeric(18,8))
    fees:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    fx_rate_at_acquisition:Mapped[Decimal]=mapped_column(Numeric(18,8),default=Decimal("1"))
    source_type:Mapped[str]=mapped_column(String(40),default="trade")
    source_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)
    tax_metadata_json:Mapped[str]=mapped_column(Text,default="{}")

class LotDisposal(Base):
    __tablename__="lot_disposal"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    trade_id:Mapped[str]=mapped_column(ForeignKey("trade.id",ondelete="CASCADE"),index=True)
    tax_lot_id:Mapped[str]=mapped_column(ForeignKey("tax_lot.id",ondelete="CASCADE"),index=True)
    quantity:Mapped[Decimal]=mapped_column(Numeric(24,10))
    cost_basis:Mapped[Decimal]=mapped_column(Numeric(18,4))
    realized_pnl:Mapped[Decimal]=mapped_column(Numeric(18,4))
    allocation_rule:Mapped[str]=mapped_column(String(40),default="FIFO")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class MortgageProfileExtra(Base, TimestampMixin):
    __tablename__="mortgage_profile_extra"
    __table_args__=(UniqueConstraint("mortgage_id",name="uq_mortgage_profile_extra_mortgage"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    mortgage_id:Mapped[str]=mapped_column(ForeignKey("mortgage.id",ondelete="CASCADE"),index=True)
    original_principal:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    original_term_months:Mapped[int|None]=mapped_column(Integer,nullable=True)
    start_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    maturity_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    apr_rate:Mapped[Decimal|None]=mapped_column(Numeric(8,6),nullable=True)
    reference_index:Mapped[str|None]=mapped_column(String(80),nullable=True)
    differential_rate:Mapped[Decimal|None]=mapped_column(Numeric(8,6),nullable=True)
    rate_review_months:Mapped[int|None]=mapped_column(Integer,nullable=True)
    next_review_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    opening_fee_percent:Mapped[Decimal|None]=mapped_column(Numeric(8,4),nullable=True)
    early_repayment_fee_percent:Mapped[Decimal|None]=mapped_column(Numeric(8,4),nullable=True)
    subrogation_fee_percent:Mapped[Decimal|None]=mapped_column(Numeric(8,4),nullable=True)
    cancellation_fee_percent:Mapped[Decimal|None]=mapped_column(Numeric(8,4),nullable=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)


class MortgagePaymentAllocation(Base, TimestampMixin):
    __tablename__="mortgage_payment_allocation"
    __table_args__=(UniqueConstraint("transaction_id",name="uq_mortgage_payment_transaction"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    mortgage_id:Mapped[str]=mapped_column(ForeignKey("mortgage.id",ondelete="CASCADE"),index=True)
    transaction_id:Mapped[str]=mapped_column(ForeignKey("transaction.id",ondelete="CASCADE"),index=True)
    payment_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    principal_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    interest_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    balance_before:Mapped[Decimal]=mapped_column(Numeric(18,4))
    balance_after:Mapped[Decimal]=mapped_column(Numeric(18,4))
    applied_to_balance:Mapped[bool]=mapped_column(Boolean,default=True)
    calculation_method:Mapped[str]=mapped_column(String(80),default="estimated_nominal_monthly_rate")


class InsurancePolicy(Base, TimestampMixin):
    __tablename__="insurance_policy"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    account_id:Mapped[str|None]=mapped_column(ForeignKey("account.id",ondelete="SET NULL"),nullable=True,index=True)
    contract_id:Mapped[str|None]=mapped_column(ForeignKey("contract.id",ondelete="SET NULL"),nullable=True)
    policy_number_masked:Mapped[str|None]=mapped_column(String(80),nullable=True)
    insurance_type:Mapped[str]=mapped_column(String(60),index=True)
    annual_premium:Mapped[Decimal]=mapped_column(Numeric(18,4))
    deductible:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    insured_object_json:Mapped[str]=mapped_column(Text,default="{}")

class CoverageFact(Base, TimestampMixin):
    __tablename__="coverage_fact"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    contract_id:Mapped[str|None]=mapped_column(ForeignKey("contract.id",ondelete="CASCADE"),nullable=True,index=True)
    insurance_policy_id:Mapped[str|None]=mapped_column(ForeignKey("insurance_policy.id",ondelete="CASCADE"),nullable=True,index=True)
    coverage_type:Mapped[str]=mapped_column(String(100),index=True)
    limit_amount:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    deductible:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    conditions_json:Mapped[str]=mapped_column(Text,default="{}")
    exclusions_json:Mapped[str]=mapped_column(Text,default="{}")
    effective_from:Mapped[date|None]=mapped_column(Date,nullable=True)
    effective_to:Mapped[date|None]=mapped_column(Date,nullable=True)
    source_document_id:Mapped[str|None]=mapped_column(ForeignKey("document.id",ondelete="SET NULL"),nullable=True)
    source_page:Mapped[int|None]=mapped_column(Integer,nullable=True)
    confidence:Mapped[Decimal]=mapped_column(Numeric(5,4),default=Decimal("0"))
    user_verified:Mapped[bool]=mapped_column(Boolean,default=False)

class CoverageOverlap(Base, TimestampMixin):
    __tablename__="coverage_overlap"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    coverage_type:Mapped[str]=mapped_column(String(100))
    left_coverage_fact_id:Mapped[str]=mapped_column(ForeignKey("coverage_fact.id",ondelete="CASCADE"))
    right_coverage_fact_id:Mapped[str]=mapped_column(ForeignKey("coverage_fact.id",ondelete="CASCADE"))
    overlap_type:Mapped[str]=mapped_column(String(40))
    estimated_redundant_cost:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    confidence:Mapped[Decimal]=mapped_column(Numeric(5,4),default=Decimal("0"))
    status:Mapped[str]=mapped_column(String(30),default="review")

class CostCenter(Base, TimestampMixin):
    __tablename__="cost_center"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    center_type:Mapped[str]=mapped_column(String(60))
    parent_id:Mapped[str|None]=mapped_column(ForeignKey("cost_center.id"),nullable=True)
    metadata_json:Mapped[str]=mapped_column(Text,default="{}")

class CostCenterLink(Base):
    __tablename__="cost_center_link"
    __table_args__=(UniqueConstraint("cost_center_id","entity_type","entity_id",name="uq_cost_center_entity"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    cost_center_id:Mapped[str]=mapped_column(ForeignKey("cost_center.id",ondelete="CASCADE"),index=True)
    entity_type:Mapped[str]=mapped_column(String(60))
    entity_id:Mapped[str]=mapped_column(String(36))
    allocation_percentage:Mapped[Decimal]=mapped_column(Numeric(6,3),default=Decimal("100"))

class DecisionAlternative(Base, TimestampMixin):
    __tablename__="decision_alternative"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    decision_case_id:Mapped[str]=mapped_column(ForeignKey("decision_case.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(180))
    one_off_cost:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    monthly_cost:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    expected_benefit:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    net_benefit:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    break_even_months:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    risk_level:Mapped[str]=mapped_column(String(20),default="unknown")
    horizon_results_json:Mapped[str]=mapped_column(Text,default="{}")
    uncertainties_json:Mapped[str]=mapped_column(Text,default="[]")

class DecisionOutcome(Base, TimestampMixin):
    __tablename__="decision_outcome"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    decision_case_id:Mapped[str]=mapped_column(ForeignKey("decision_case.id",ondelete="CASCADE"),index=True)
    selected_alternative_id:Mapped[str|None]=mapped_column(ForeignKey("decision_alternative.id",ondelete="SET NULL"),nullable=True)
    observation_start:Mapped[date]=mapped_column(Date)
    observation_end:Mapped[date]=mapped_column(Date)
    expected_impact_json:Mapped[str]=mapped_column(Text,default="{}")
    observed_impact_json:Mapped[str]=mapped_column(Text,default="{}")
    variance_json:Mapped[str]=mapped_column(Text,default="{}")
    explanation:Mapped[str|None]=mapped_column(Text,nullable=True)
    data_completeness:Mapped[Decimal]=mapped_column(Numeric(5,4),default=Decimal("0"))

class RepairIssue(Base, TimestampMixin):
    __tablename__="repair_issue"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    issue_type:Mapped[str]=mapped_column(String(80),index=True)
    entity_type:Mapped[str|None]=mapped_column(String(80),nullable=True)
    entity_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    severity:Mapped[str]=mapped_column(String(20),default="medium")
    status:Mapped[str]=mapped_column(String(30),default="open")
    repair_action:Mapped[str]=mapped_column(String(80))
    metadata_json:Mapped[str]=mapped_column(Text,default="{}")
    detected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class DocumentChunk(Base, TimestampMixin):
    __tablename__="document_chunk"
    __table_args__=(UniqueConstraint("document_id","chunk_index",name="uq_document_chunk"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    document_id:Mapped[str]=mapped_column(ForeignKey("document.id",ondelete="CASCADE"),index=True)
    page_start:Mapped[int|None]=mapped_column(Integer,nullable=True)
    page_end:Mapped[int|None]=mapped_column(Integer,nullable=True)
    heading:Mapped[str|None]=mapped_column(String(255),nullable=True)
    section:Mapped[str|None]=mapped_column(String(255),nullable=True)
    text:Mapped[str]=mapped_column(Text)
    token_count:Mapped[int]=mapped_column(Integer,default=0)
    chunk_index:Mapped[int]=mapped_column(Integer)
    embedding_model:Mapped[str|None]=mapped_column(String(120),nullable=True)
    embedding_version:Mapped[str|None]=mapped_column(String(40),nullable=True)
    embedding_json:Mapped[str|None]=mapped_column(Text,nullable=True)

class MarketPrice(Base):
    __tablename__="market_price"
    __table_args__=(UniqueConstraint("security_id","timestamp","provider",name="uq_market_price"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    timestamp:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    close:Mapped[Decimal]=mapped_column(Numeric(18,8))
    currency:Mapped[str]=mapped_column(String(3))
    provider:Mapped[str]=mapped_column(String(80))
    fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    is_delayed:Mapped[bool]=mapped_column(Boolean,default=True)

class NewsItem(Base):
    __tablename__="news_item"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    canonical_url:Mapped[str]=mapped_column(Text,unique=True)
    source:Mapped[str]=mapped_column(String(120),index=True)
    headline:Mapped[str]=mapped_column(Text)
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    event_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    summary:Mapped[str|None]=mapped_column(Text,nullable=True)
    reliability:Mapped[Decimal]=mapped_column(Numeric(5,4),default=Decimal("0.5"))
    fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class BackupRecord(Base):
    __tablename__="backup_record"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    file_path:Mapped[str]=mapped_column(Text)
    sha256:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    verified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    format_version:Mapped[int]=mapped_column(Integer,default=1)


class CorporateAction(Base,TimestampMixin):
    __tablename__="corporate_action"
    __table_args__=(UniqueConstraint("portfolio_id","security_id","action_type","effective_date","source_ref",name="uq_corporate_action_source"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    portfolio_id:Mapped[str]=mapped_column(ForeignKey("portfolio.id",ondelete="CASCADE"),index=True)
    security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True)
    action_type:Mapped[str]=mapped_column(String(30),index=True)
    effective_date:Mapped[date]=mapped_column(Date,index=True)
    value:Mapped[Decimal]=mapped_column(Numeric(24,10))
    currency:Mapped[str]=mapped_column(String(3),default="EUR")
    source_type:Mapped[str]=mapped_column(String(40),default="manual")
    source_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    applied:Mapped[bool]=mapped_column(Boolean,default=False)
