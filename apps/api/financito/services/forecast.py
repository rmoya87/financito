from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..domain.engines import comparable_period_last_year, money
from ..models import Account, Commitment, Transaction
from .financial_analytics import cash_flow


@dataclass(frozen=True)
class ForecastResult:
    horizon_start: date
    horizon_end: date
    baseline_start: date
    baseline_end: date
    predicted_income: Decimal
    predicted_expenses: Decimal
    predicted_savings: Decimal
    predicted_min_liquidity: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    known_commitments: Decimal
    historical_baseline: Decimal
    model_version: str


MODEL_VERSION = "seasonal-commitments-v1"


def _sum_transactions(session: Session, start: date, end: date, positive: bool) -> Decimal:
    flow = cash_flow(session, start, end)
    return flow["income"] if positive else flow["expenses"]


def forecast(session: Session, start: date, end: date) -> ForecastResult:
    if end < start:
        raise ValueError("horizon_end must be >= horizon_start")
    ly_start, ly_end = comparable_period_last_year(start, end)
    baseline_expenses = _sum_transactions(session, ly_start, ly_end, False)
    baseline_income = _sum_transactions(session, ly_start, ly_end, True)

    days = (end - start).days + 1
    recent_end = start.fromordinal(start.toordinal() - 1)
    recent_start = recent_end.fromordinal(max(date.min.toordinal(), recent_end.toordinal() - min(days, 90) + 1))
    recent_expenses = _sum_transactions(session, recent_start, recent_end, False)
    recent_income = _sum_transactions(session, recent_start, recent_end, True)
    recent_days = max(1, (recent_end - recent_start).days + 1)
    recent_expenses = recent_expenses * Decimal(days) / Decimal(recent_days)
    recent_income = recent_income * Decimal(days) / Decimal(recent_days)

    # Same-period-last-year remains the anchor. Recent trend only nudges within ±20%.
    def adjusted(baseline: Decimal, recent: Decimal) -> Decimal:
        if baseline <= 0:
            return recent
        if recent <= 0:
            return baseline
        ratio = recent / baseline
        ratio = max(Decimal("0.80"), min(Decimal("1.20"), ratio))
        return baseline * ratio

    commitments = session.scalars(select(Commitment).where(
        and_(Commitment.due_date >= start, Commitment.due_date <= end, Commitment.status == "active")
    )).all()
    known_commitments = sum((c.amount for c in commitments), Decimal("0"))
    predicted_expenses = adjusted(baseline_expenses, recent_expenses) + known_commitments
    predicted_income = adjusted(baseline_income, recent_income)
    predicted_savings = predicted_income - predicted_expenses
    balances = sum((a.current_balance for a in session.scalars(select(Account)).all()), Decimal("0"))
    min_liquidity = balances + min(Decimal("0"), predicted_savings)

    uncertainty = max(predicted_expenses * Decimal("0.10"), Decimal("50"))
    return ForecastResult(
        start, end, ly_start, ly_end,
        money(predicted_income), money(predicted_expenses), money(predicted_savings), money(min_liquidity),
        money(max(Decimal("0"), predicted_expenses - uncertainty)), money(predicted_expenses + uncertainty),
        money(known_commitments), money(baseline_expenses), MODEL_VERSION,
    )
