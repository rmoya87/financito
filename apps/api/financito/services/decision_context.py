from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Contract, Mortgage, Portfolio
from .investment_tracking import tracked_assets
from .wealth import summary as wealth_summary
from .evidence import structured_evidence_context
from .financial_analytics import cash_flow
from .insurance_analysis import insurance_verdict
from ..domain.portfolio import portfolio_summary


def mortgage_row(row: Mortgage) -> dict:
    return {
        "id": row.id,
        "lender": row.lender,
        "remaining_principal": str(row.remaining_principal),
        "currency": row.currency,
        "interest_type": row.interest_type,
        "nominal_rate": str(row.nominal_rate),
        "monthly_payment": str(row.monthly_payment),
        "remaining_months": row.remaining_months,
        "early_repayment_fee": None if row.early_repayment_fee is None else str(row.early_repayment_fee),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def live_decision_context(session: Session) -> dict:
    mortgages = [mortgage_row(row) for row in session.scalars(select(Mortgage).order_by(Mortgage.updated_at.desc())).all()]
    contracts = [
        {
            "id": row.id,
            "provider_name": row.provider_name,
            "contract_type": row.contract_type,
            "renewal_date": None if row.renewal_date is None else str(row.renewal_date),
            "cancellation_notice_days": row.cancellation_notice_days,
            "early_exit_penalty": None if row.early_exit_penalty is None else str(row.early_exit_penalty),
            "annual_cost": None if row.annual_cost is None else str(row.annual_cost),
            "evidence_status": row.evidence_status,
        }
        for row in session.scalars(select(Contract).order_by(Contract.updated_at.desc())).all()
    ]
    portfolios = [
        {
            "id": row.id,
            "name": row.name,
            "base_currency": row.base_currency,
            **portfolio_summary(session, row.id),
        }
        for row in session.scalars(select(Portfolio)).all()
    ]
    accounts = [
        {
            "id": row.id,
            "name": row.name,
            "institution_name": row.institution_name,
            "current_balance": str(row.current_balance),
            "available_balance": None if row.available_balance is None else str(row.available_balance),
            "currency": row.currency,
        }
        for row in session.scalars(select(Account)).all()
    ]
    liquidity = sum((row.current_balance for row in session.scalars(select(Account)).all()), Decimal("0"))
    today=date.today()
    month_flow=cash_flow(session,today.replace(day=1),today)
    trailing_start=today-timedelta(days=89)
    trailing_flow=cash_flow(session,trailing_start,today)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "real_data_only": True,
        "liquidity": str(liquidity),
        "cash_flow_current_month":{
            "start":str(today.replace(day=1)),
            "end":str(today),
            "income":str(month_flow["income"]),
            "expenses":str(month_flow["expenses"]),
            "savings":str(month_flow["savings"]),
            "savings_rate":None if month_flow["savings_rate"] is None else str(month_flow["savings_rate"]),
        },
        "cash_flow_last_90_days":{
            "start":str(trailing_start),
            "end":str(today),
            "income":str(trailing_flow["income"]),
            "expenses":str(trailing_flow["expenses"]),
            "savings":str(trailing_flow["savings"]),
            "savings_rate":None if trailing_flow["savings_rate"] is None else str(trailing_flow["savings_rate"]),
            "average_monthly_income":str((trailing_flow["income"]/Decimal("3")).quantize(Decimal("0.01"))),
            "average_monthly_expenses":str((trailing_flow["expenses"]/Decimal("3")).quantize(Decimal("0.01"))),
            "average_monthly_savings":str((trailing_flow["savings"]/Decimal("3")).quantize(Decimal("0.01"))),
        },
        "wealth": wealth_summary(session),
        "accounts": accounts,
        "mortgages": mortgages,
        "contracts": contracts,
        "portfolios": portfolios,
        "tracked_assets": tracked_assets(session),
        "document_evidence": structured_evidence_context(session),
        "insurance": insurance_verdict(session,use_ai=False),
        "rules": [
            "Los cálculos deterministas usan registros guardados en Financito; no valores de ejemplo.",
            "Los precios de mercado se identifican con proveedor y fecha. Si falta precio real, el valor se marca como no disponible.",
            "Ingresos, gastos y ahorro proceden de movimientos reales, excluyendo transferencias internas y tratando reembolsos como reducción de gasto.",
            "La senda de tipos y las alternativas futuras son supuestos explícitos; el punto de partida hipotecario procede de la hipoteca guardada.",
            "La evidencia documental inferida no sustituye a un dato confirmado por el usuario.",
        ],
    }
