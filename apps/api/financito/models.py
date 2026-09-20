from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uuid_str() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Account(Base, TimestampMixin):
    __tablename__ = "account"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    institution_name: Mapped[str] = mapped_column(String(120), default="Manual")
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(40), default="checking")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    iban_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    available_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    sync_status: Mapped[str] = mapped_column(String(30), default="local")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Category(Base, TimestampMixin):
    __tablename__ = "category"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    system_key: Mapped[str] = mapped_column(String(100), unique=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("category.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transaction"
    __table_args__ = (UniqueConstraint("account_id", "duplicate_fingerprint", name="uq_tx_fingerprint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    description_raw: Mapped[str] = mapped_column(Text)
    description_normalized: Mapped[str] = mapped_column(Text)
    merchant_raw: Mapped[str | None] = mapped_column(String(240), nullable=True)
    merchant_normalized: Mapped[str | None] = mapped_column(String(240), nullable=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("category.id"), nullable=True, index=True)
    categorization_method: Mapped[str] = mapped_column(String(40), default="unclassified")
    categorization_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    user_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_internal_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_extraordinary: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_fingerprint: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(40), default="import")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account: Mapped[Account] = relationship(back_populates="transactions")
    category: Mapped[Category | None] = relationship()


class CategorizationAudit(Base):
    __tablename__ = "categorization_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transaction.id", ondelete="CASCADE"), index=True)
    previous_category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    method: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1"))
    changed_by: Mapped[str] = mapped_column(String(40), default="user")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Budget(Base, TimestampMixin):
    __tablename__ = "budget"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    category_id: Mapped[str] = mapped_column(ForeignKey("category.id"))
    period_type: Mapped[str] = mapped_column(String(20), default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    alert_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.8"))


class Commitment(Base, TimestampMixin):
    __tablename__ = "commitment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    commitment_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(180))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    recurrence: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1"))
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    cancellable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="active")


class ForecastRun(Base):
    __tablename__ = "forecast_run"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    horizon_start: Mapped[date] = mapped_column(Date)
    horizon_end: Mapped[date] = mapped_column(Date)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40))
    scenario: Mapped[str] = mapped_column(String(20), default="base")
    predicted_income: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    predicted_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    predicted_savings: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    predicted_min_liquidity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    baseline_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    baseline_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    assumptions_json: Mapped[str] = mapped_column(Text, default="{}")


class Document(Base, TimestampMixin):
    __tablename__ = "document"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    file_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    document_type: Mapped[str] = mapped_column(String(60), default="unknown")
    status: Mapped[str] = mapped_column(String(30), default="indexed")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    excluded_from_ai: Mapped[bool] = mapped_column(Boolean, default=False)


class ExtractedFact(Base, TimestampMixin):
    __tablename__ = "extracted_fact"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    fact_type: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(100))
    value_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(30), default="inferred")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Contract(Base, TimestampMixin):
    __tablename__ = "contract"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider_name: Mapped[str] = mapped_column(String(180))
    contract_type: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    permanence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    early_exit_penalty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    annual_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    evidence_status: Mapped[str] = mapped_column(String(30), default="needs_more_data")


class Mortgage(Base, TimestampMixin):
    __tablename__ = "mortgage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    lender: Mapped[str] = mapped_column(String(180))
    remaining_principal: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    interest_type: Mapped[str] = mapped_column(String(20), default="fixed")
    nominal_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    remaining_months: Mapped[int] = mapped_column(Integer)
    early_repayment_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)


class Portfolio(Base, TimestampMixin):
    __tablename__ = "portfolio"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120))
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR")


class Security(Base, TimestampMixin):
    __tablename__ = "security"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_class: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")


class Position(Base, TimestampMixin):
    __tablename__ = "position"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolio.id", ondelete="CASCADE"))
    security_id: Mapped[str] = mapped_column(ForeignKey("security.id", ondelete="CASCADE"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)


class FinancialGoal(Base, TimestampMixin):
    __tablename__ = "financial_goal"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    goal_type: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(180))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    current_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    planned_monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), default="active")


class OptimizationOpportunity(Base, TimestampMixin):
    __tablename__ = "optimization_opportunity"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    category: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(180))
    gross_annual_saving: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    switching_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    penalties: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    lost_benefits: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    additional_recurring_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    tax_impact: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    net_annual_benefit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    break_even_months: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(30), default="needs_more_data")


class ActionItem(Base, TimestampMixin):
    __tablename__ = "action_item"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    action_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(220))
    related_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    expected_impact_json: Mapped[str] = mapped_column(Text, default="{}")
    source_type: Mapped[str] = mapped_column(String(40), default="system")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DecisionCase(Base, TimestampMixin):
    __tablename__ = "decision_case"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    decision_type: Mapped[str] = mapped_column(String(80))
    question: Mapped[str] = mapped_column(Text)
    current_state_json: Mapped[str] = mapped_column(Text, default="{}")
    assumptions_json: Mapped[str] = mapped_column(Text, default="{}")
    constraints_json: Mapped[str] = mapped_column(Text, default="{}")
    calculation_version: Mapped[str] = mapped_column(String(40), default="v1")
    status: Mapped[str] = mapped_column(String(30), default="draft")


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
