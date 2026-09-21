from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, ActionItem, Budget, Category, Commitment, Contract, Mortgage, Portfolio
from ..models_analytics import Anomaly
from ..domain.portfolio import portfolio_summary
from .contractual_costs import switching_readiness
from .evidence import structured_evidence_context
from .financial_analytics import cash_flow, category_spending
from .insurance_analysis import insurance_verdict
from .investment_tracking import tracked_assets
from .mortgage_cost import current_remaining_apr_estimate, rate_review_readiness
from .wealth import summary as wealth_summary


def mortgage_row(row: Mortgage) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
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


def _mortgage_decision_row(session: Session, row: Mortgage) -> dict:
    return {
        **mortgage_row(row),
        "current_remaining_apr": current_remaining_apr_estimate(session, row),
        "rate_review": rate_review_readiness(session, row),
        "switching_readiness": switching_readiness(session, row.id),
    }


def _budget_context(
    session: Session,
    today: date,
    account_id: str | None = None,
    account_type: str | None = None,
) -> tuple[list[dict], list[dict]]:
    categories = {row.id: row for row in session.scalars(select(Category)).all()}
    budgets = session.scalars(select(Budget)).all()
    spending_cache: dict[tuple[date, date], dict[str, Decimal]] = {}
    rows: list[dict] = []
    alerts: list[dict] = []
    for budget in budgets:
        start = date(today.year, 1, 1) if budget.period_type == "annual" else today.replace(day=1)
        cache_key = (start, today)
        if cache_key not in spending_cache:
            spending_cache[cache_key] = {
                item["category_id"]: item["amount"]
                for item in category_spending(session, start, today, account_id, account_type)
            }
        actual = spending_cache[cache_key].get(budget.category_id, Decimal("0"))
        target = budget.amount
        threshold = budget.alert_threshold
        utilization = None if target <= 0 else (actual / target)
        category = categories.get(budget.category_id)
        row = {
            "id": budget.id,
            "category_id": budget.category_id,
            "category": category.name if category else "Categoría",
            "system_key": category.system_key if category else "other",
            "period_type": budget.period_type,
            "period_start": str(start),
            "period_end": str(today),
            "budget": str(target),
            "actual": str(actual.quantize(Decimal("0.01"))),
            "remaining": str((target - actual).quantize(Decimal("0.01"))),
            "alert_threshold": str(threshold),
            "utilization": None if utilization is None else str(utilization.quantize(Decimal("0.0001"))),
            "currency": budget.currency,
        }
        rows.append(row)
        threshold_amount = target * threshold
        triggered = actual > 0 and (target <= 0 or actual >= threshold_amount)
        if triggered:
            over = actual > target
            alerts.append({
                "id": "budget:" + budget.id,
                "kind": "budget",
                "severity": "high" if over else "medium",
                "title": (
                    f"Presupuesto superado · {row['category']}"
                    if over else f"Presupuesto cerca del límite · {row['category']}"
                ),
                "detail": (
                    f"{actual.quantize(Decimal('0.01'))} € gastados de {target.quantize(Decimal('0.01'))} € "
                    f"en el periodo {start.isoformat()}–{today.isoformat()}."
                ),
                "action_path": "/analytics/",
                "source_id": budget.id,
            })
    return rows, alerts


def _anomaly_context(session: Session) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    alerts: list[dict] = []
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.status == "open").order_by(Anomaly.created_at.desc()).limit(50)
    ).all()
    for anomaly in anomalies:
        try:
            observed = json.loads(anomaly.observed_json or "{}")
        except Exception:
            observed = {}
        item = {
            "id": anomaly.id,
            "transaction_id": anomaly.transaction_id,
            "anomaly_type": anomaly.anomaly_type,
            "explanation": anomaly.explanation,
            "confidence": str(anomaly.confidence),
            "observed": observed,
            "created_at": anomaly.created_at.isoformat() if anomaly.created_at else None,
        }
        rows.append(item)
        alerts.append({
            "id": "anomaly:" + anomaly.id,
            "kind": "transaction_anomaly",
            "severity": "medium",
            "title": "Movimiento fuera de patrón",
            "detail": anomaly.explanation,
            "action_path": "/transactions/",
            "source_id": anomaly.transaction_id,
        })
    return rows, alerts


def _action_rows(session: Session) -> list[dict]:
    rows = session.scalars(
        select(ActionItem)
        .where(ActionItem.status.in_(["pending", "in_progress"]))
        .order_by(ActionItem.due_date.asc().nullslast(), ActionItem.created_at.desc())
        .limit(50)
    ).all()
    result = []
    for row in rows:
        try:
            impact = json.loads(row.expected_impact_json or "{}")
        except Exception:
            impact = {}
        result.append({
            "id": row.id,
            "title": row.title,
            "action_type": row.action_type,
            "priority": row.priority,
            "status": row.status,
            "due_date": None if row.due_date is None else str(row.due_date),
            "notes": row.notes,
            "related_entity_type": row.related_entity_type,
            "related_entity_id": row.related_entity_id,
            "expected_impact": impact,
        })
    return result


def live_decision_context(
    session: Session,
    *,
    start: date | None = None,
    end: date | None = None,
    account_id: str | None = None,
    account_type: str | None = None,
) -> dict:
    scope_ids=None
    if account_id:
        scope_ids={account_id}
    elif account_type:
        scope_ids=set(session.scalars(select(Account.id).where(Account.account_type==account_type)).all())

    mortgage_stmt=select(Mortgage).order_by(Mortgage.updated_at.desc())
    if scope_ids is not None:
        mortgage_stmt=mortgage_stmt.where(Mortgage.account_id.in_(scope_ids))
    mortgage_records = session.scalars(mortgage_stmt).all()
    mortgages = [_mortgage_decision_row(session, row) for row in mortgage_records]
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
            "account_id": row.account_id,
            **portfolio_summary(session, row.id),
        }
        for row in session.scalars(
            select(Portfolio) if scope_ids is None else select(Portfolio).where(Portfolio.account_id.in_(scope_ids))
        ).all()
    ]
    account_stmt=select(Account)
    if scope_ids is not None:
        account_stmt=account_stmt.where(Account.id.in_(scope_ids))
    account_records = session.scalars(account_stmt).all()
    accounts = [
        {
            "id": row.id,
            "name": row.name,
            "institution_name": row.institution_name,
            "account_type": row.account_type,
            "current_balance": str(row.current_balance),
            "available_balance": None if row.available_balance is None else str(row.available_balance),
            "currency": row.currency,
        }
        for row in account_records
    ]
    liquidity = sum((row.current_balance for row in account_records), Decimal("0"))
    today = end or date.today()
    month_start = today.replace(day=1)
    period_start = start or month_start
    period_flow = cash_flow(session, period_start, today, account_id, account_type)
    month_flow = cash_flow(session, month_start, today, account_id, account_type)
    trailing_start = today - timedelta(days=89)
    trailing_flow = cash_flow(session, trailing_start, today, account_id, account_type)
    budgets, budget_alerts = _budget_context(session, today, account_id, account_type)
    anomalies, anomaly_alerts = _anomaly_context(session)
    actions = _action_rows(session)
    commitments = [
        {
            "id": row.id,
            "title": row.title,
            "type": row.commitment_type,
            "amount": str(row.amount),
            "currency": row.currency,
            "due_date": str(row.due_date),
            "confidence": str(row.confidence),
            "mandatory": row.mandatory,
            "cancellable": row.cancellable,
        }
        for row in session.scalars(
            select(Commitment)
            .where(
                Commitment.status == "active",
                Commitment.due_date >= today,
                Commitment.due_date <= today + timedelta(days=90),
                *(
                    [Commitment.account_id.in_(scope_ids)]
                    if scope_ids is not None else []
                ),
            )
            .order_by(Commitment.due_date)
        ).all()
    ]
    decision_alerts = sorted(
        budget_alerts + anomaly_alerts,
        key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item["severity"], 3),
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "real_data_only": True,
        "liquidity": str(liquidity),
        "cash_flow_current_period": {
            "start": str(period_start),
            "end": str(today),
            "income": str(period_flow["income"]),
            "expenses": str(period_flow["expenses"]),
            "savings": str(period_flow["savings"]),
            "savings_rate": None if period_flow["savings_rate"] is None else str(period_flow["savings_rate"]),
        },
        "cash_flow_current_month": {
            "start": str(month_start),
            "end": str(today),
            "income": str(month_flow["income"]),
            "expenses": str(month_flow["expenses"]),
            "savings": str(month_flow["savings"]),
            "savings_rate": None if month_flow["savings_rate"] is None else str(month_flow["savings_rate"]),
        },
        "cash_flow_last_90_days": {
            "start": str(trailing_start),
            "end": str(today),
            "income": str(trailing_flow["income"]),
            "expenses": str(trailing_flow["expenses"]),
            "savings": str(trailing_flow["savings"]),
            "savings_rate": None if trailing_flow["savings_rate"] is None else str(trailing_flow["savings_rate"]),
            "average_monthly_income": str((trailing_flow["income"] / Decimal("3")).quantize(Decimal("0.01"))),
            "average_monthly_expenses": str((trailing_flow["expenses"] / Decimal("3")).quantize(Decimal("0.01"))),
            "average_monthly_savings": str((trailing_flow["savings"] / Decimal("3")).quantize(Decimal("0.01"))),
        },
        "wealth": wealth_summary(session,account_id,account_type),
        "accounts": accounts,
        "mortgages": mortgages,
        "contracts": contracts,
        "portfolios": portfolios,
        "tracked_assets": [
            row for row in tracked_assets(session)
            if scope_ids is None or set(row.get("portfolio_ids") or []).intersection({
                p.id for p in session.scalars(select(Portfolio).where(Portfolio.account_id.in_(scope_ids))).all()
            })
        ],
        "document_evidence": structured_evidence_context(session),
        "insurance": insurance_verdict(
            session,use_ai=False,start=period_start,end=today,
            account_id=account_id,account_type=account_type,
        ),
        "budgets": budgets,
        "anomalies": anomalies,
        "commitments_next_90_days": commitments,
        "actions": actions,
        "decision_alerts": decision_alerts,
        "rules": [
            "Los cálculos deterministas usan registros guardados en Financito; no valores de ejemplo.",
            "Hipoteca, seguros, contratos, movimientos, presupuestos, anomalías y acciones comparten este mismo contexto de decisión.",
            "Los precios de mercado se identifican con proveedor y fecha. Si falta precio real, el valor se marca como no disponible.",
            "Ingresos, gastos y ahorro proceden de movimientos reales, excluyendo transferencias internas y tratando reembolsos como reducción de gasto.",
            "El coste hipotecario efectivo restante incluye únicamente costes futuros vinculados conocidos; no vuelve a cargar costes hundidos.",
            "La senda de tipos y las alternativas futuras son supuestos explícitos; el punto de partida hipotecario procede de la hipoteca guardada.",
            "La evidencia documental inferida no sustituye a un dato confirmado por el usuario.",
            "Una penalización, coste de entrada o cobertura desconocidos no se interpretan como cero.",
        ],
    }
