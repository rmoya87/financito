from __future__ import annotations
from datetime import date,datetime,timezone
from decimal import Decimal
from sqlalchemy import Boolean,Date,DateTime,ForeignKey,Integer,Numeric,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
from .models import TimestampMixin,uuid_str

def utcnow():return datetime.now(timezone.utc)
class RecurringSeries(Base,TimestampMixin):
    __tablename__="recurring_series"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    merchant_normalized:Mapped[str]=mapped_column(String(240),index=True)
    cadence:Mapped[str]=mapped_column(String(30))
    expected_amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    amount_tolerance:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    next_expected_date:Mapped[date]=mapped_column(Date,index=True)
    confidence:Mapped[Decimal]=mapped_column(Numeric(5,4))
    status:Mapped[str]=mapped_column(String(30),default="active")
class TransactionRule(Base,TimestampMixin):
    __tablename__="transaction_rule"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    priority:Mapped[int]=mapped_column(Integer,default=100,index=True)
    matcher_type:Mapped[str]=mapped_column(String(30))
    matcher_value:Mapped[str]=mapped_column(String(255))
    category_id:Mapped[str]=mapped_column(ForeignKey("category.id"))
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class TransactionSplit(Base,TimestampMixin):
    __tablename__="transaction_split"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    transaction_id:Mapped[str]=mapped_column(ForeignKey("transaction.id",ondelete="CASCADE"),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(18,4))
    category_id:Mapped[str]=mapped_column(ForeignKey("category.id"))
    note:Mapped[str|None]=mapped_column(Text,nullable=True)
class Anomaly(Base,TimestampMixin):
    __tablename__="anomaly"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    transaction_id:Mapped[str]=mapped_column(ForeignKey("transaction.id",ondelete="CASCADE"),index=True)
    anomaly_type:Mapped[str]=mapped_column(String(60))
    baseline_json:Mapped[str]=mapped_column(Text,default="{}")
    observed_json:Mapped[str]=mapped_column(Text,default="{}")
    explanation:Mapped[str]=mapped_column(Text)
    confidence:Mapped[Decimal]=mapped_column(Numeric(5,4))
    status:Mapped[str]=mapped_column(String(30),default="open")
class BankingConnection(Base,TimestampMixin):
    __tablename__="banking_connection"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    provider:Mapped[str]=mapped_column(String(60),default="enable_banking")
    session_id:Mapped[str]=mapped_column(String(120),unique=True)
    bank_name:Mapped[str]=mapped_column(String(180))
    country:Mapped[str]=mapped_column(String(2),default="ES")
    consent_expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default="active")
    metadata_json:Mapped[str]=mapped_column(Text,default="{}")
class Benefit(Base,TimestampMixin):
    __tablename__="benefit"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    contract_id:Mapped[str|None]=mapped_column(ForeignKey("contract.id",ondelete="CASCADE"),nullable=True,index=True)
    name:Mapped[str]=mapped_column(String(180))
    benefit_type:Mapped[str]=mapped_column(String(60))
    theoretical_value:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    realized_value:Mapped[Decimal]=mapped_column(Numeric(18,4),default=Decimal("0"))
    user_adjusted_value:Mapped[Decimal|None]=mapped_column(Numeric(18,4),nullable=True)
    period:Mapped[str]=mapped_column(String(30),default="annual")
class LinkedProduct(Base,TimestampMixin):
    __tablename__="linked_product"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    parent_product_type:Mapped[str]=mapped_column(String(60));parent_product_id:Mapped[str]=mapped_column(String(36))
    linked_product_type:Mapped[str]=mapped_column(String(60));linked_product_id:Mapped[str]=mapped_column(String(36))
    discount_value:Mapped[Decimal]=mapped_column(Numeric(18,6),default=Decimal("0"))
    discount_unit:Mapped[str]=mapped_column(String(30),default="currency")
    conditions:Mapped[str]=mapped_column(Text,default="")
class EntityLink(Base,TimestampMixin):
    __tablename__="entity_link"
    __table_args__=(UniqueConstraint("from_type","from_id","relation_type","to_type","to_id",name="uq_entity_link"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str)
    from_type:Mapped[str]=mapped_column(String(60));from_id:Mapped[str]=mapped_column(String(36));relation_type:Mapped[str]=mapped_column(String(80));to_type:Mapped[str]=mapped_column(String(60));to_id:Mapped[str]=mapped_column(String(36))
    confidence:Mapped[Decimal]=mapped_column(Numeric(5,4),default=Decimal("1"));source_type:Mapped[str]=mapped_column(String(40),default="manual");source_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)
class FundamentalSnapshot(Base):
    __tablename__="fundamental_snapshot"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str);security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True);period:Mapped[str]=mapped_column(String(30));revenue:Mapped[Decimal|None]=mapped_column(Numeric(22,4),nullable=True);net_income:Mapped[Decimal|None]=mapped_column(Numeric(22,4),nullable=True);eps:Mapped[Decimal|None]=mapped_column(Numeric(18,6),nullable=True);fcf:Mapped[Decimal|None]=mapped_column(Numeric(22,4),nullable=True);debt:Mapped[Decimal|None]=mapped_column(Numeric(22,4),nullable=True);cash:Mapped[Decimal|None]=mapped_column(Numeric(22,4),nullable=True);ratios_json:Mapped[str]=mapped_column(Text,default="{}");provider:Mapped[str]=mapped_column(String(80));fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
class CryptoSnapshot(Base):
    __tablename__="crypto_snapshot"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str);security_id:Mapped[str]=mapped_column(ForeignKey("security.id",ondelete="CASCADE"),index=True);market_cap:Mapped[Decimal|None]=mapped_column(Numeric(24,4),nullable=True);volume:Mapped[Decimal|None]=mapped_column(Numeric(24,4),nullable=True);circulating_supply:Mapped[Decimal|None]=mapped_column(Numeric(28,8),nullable=True);max_supply:Mapped[Decimal|None]=mapped_column(Numeric(28,8),nullable=True);volatility:Mapped[Decimal|None]=mapped_column(Numeric(12,8),nullable=True);drawdown:Mapped[Decimal|None]=mapped_column(Numeric(12,8),nullable=True);metrics_json:Mapped[str]=mapped_column(Text,default="{}");provider:Mapped[str]=mapped_column(String(80));fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
class ModelEvaluationRun(Base):
    __tablename__="model_evaluation_run"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_str);model_type:Mapped[str]=mapped_column(String(60));candidate_version:Mapped[str]=mapped_column(String(120));baseline_version:Mapped[str|None]=mapped_column(String(120),nullable=True);dataset_version:Mapped[str]=mapped_column(String(120));metrics_json:Mapped[str]=mapped_column(Text);passed_gate:Mapped[bool]=mapped_column(Boolean);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
