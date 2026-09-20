from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Commitment, Transaction
from ..models_analytics import EntityLink
from .financial_analytics import cash_flow

CENT = Decimal("0.01")
MODEL_VERSION = "month-end-history-v1"


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _safe_previous_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def _refund_ids(session: Session, transaction_ids: list[str]) -> set[str]:
    if not transaction_ids:
        return set()
    return set(session.scalars(
        select(EntityLink.from_id).where(
            EntityLink.from_type == "transaction",
            EntityLink.relation_type == "refund_of",
            EntityLink.from_id.in_(transaction_ids),
        )
    ).all())


def _account_flow(session: Session, account_id: str, start: date, end: date) -> dict[str, Decimal]:
    if end < start:
        return {"income": Decimal("0"), "expenses": Decimal("0"), "savings": Decimal("0")}
    rows = session.scalars(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.booking_date >= start,
            Transaction.booking_date <= end,
            Transaction.is_internal_transfer.is_(False),
        )
    ).all()
    refunds = _refund_ids(session, [row.id for row in rows])
    income = Decimal("0")
    expenses = Decimal("0")
    for row in rows:
        if row.id in refunds and row.amount > 0:
            expenses -= row.amount
        elif row.amount >= 0:
            income += row.amount
        else:
            expenses += -row.amount
    expenses = max(Decimal("0"), expenses)
    return {
        "income": income,
        "expenses": expenses,
        "savings": income - expenses,
    }


def _blend(same_period: Decimal, recent_scaled: Decimal, has_same_period: bool, has_recent: bool) -> Decimal:
    if has_same_period and has_recent:
        return same_period * Decimal("0.70") + recent_scaled * Decimal("0.30")
    if has_same_period:
        return same_period
    if has_recent:
        return recent_scaled
    return Decimal("0")


def _remaining_projection_for_account(
    session: Session,
    account_id: str,
    as_of: date,
    end: date,
) -> dict[str, Decimal | int | str]:
    remaining_start = as_of + timedelta(days=1)
    remaining_days = max(0, (end - as_of).days)
    if remaining_days == 0:
        return {
            "income": Decimal("0"),
            "expenses": Decimal("0"),
            "history_days": 0,
            "method": "month_closed",
        }

    ly_start = _safe_previous_year(remaining_start)
    ly_end = _safe_previous_year(end)
    same = _account_flow(session, account_id, ly_start, ly_end)

    recent_end = as_of
    recent_start = recent_end - timedelta(days=59)
    recent = _account_flow(session, account_id, recent_start, recent_end)
    recent_days = max(1, (recent_end - recent_start).days + 1)
    scale = Decimal(remaining_days) / Decimal(recent_days)

    same_count = session.scalar(
        select(Transaction.id).where(
            Transaction.account_id == account_id,
            Transaction.booking_date >= ly_start,
            Transaction.booking_date <= ly_end,
        ).limit(1)
    )
    recent_count = session.scalar(
        select(Transaction.id).where(
            Transaction.account_id == account_id,
            Transaction.booking_date >= recent_start,
            Transaction.booking_date <= recent_end,
        ).limit(1)
    )

    income = _blend(same["income"], recent["income"] * scale, same_count is not None, recent_count is not None)
    expenses = _blend(same["expenses"], recent["expenses"] * scale, same_count is not None, recent_count is not None)

    method = (
        "70% mismo periodo año anterior + 30% ritmo últimos 60 días"
        if same_count is not None and recent_count is not None
        else "mismo periodo año anterior"
        if same_count is not None
        else "ritmo últimos 60 días"
        if recent_count is not None
        else "sin histórico suficiente"
    )
    return {
        "income": _money(income),
        "expenses": _money(expenses),
        "history_days": (ly_end - ly_start).days + 1 if same_count is not None else (60 if recent_count is not None else 0),
        "method": method,
    }


def _known_commitments(session: Session, start: date, end: date) -> Decimal:
    if end < start:
        return Decimal("0")
    rows = session.scalars(
        select(Commitment).where(
            Commitment.due_date >= start,
            Commitment.due_date <= end,
            Commitment.status == "active",
        )
    ).all()
    return sum((row.amount for row in rows), Decimal("0"))


def _backtest_accuracy(session: Session, as_of: date, months: int = 6) -> dict:
    expense_abs_error = Decimal("0")
    expense_actual_total = Decimal("0")
    savings_abs_error = Decimal("0")
    evaluated = 0

    cursor = as_of.replace(day=1) - timedelta(days=1)
    for _ in range(months):
        month_end = _month_end(cursor)
        cutoff_day = min(as_of.day, max(1, month_end.day - 1))
        cutoff = cursor.replace(day=cutoff_day)
        month_start = cursor.replace(day=1)

        actual = cash_flow(session, month_start, month_end)
        if actual["income"] == 0 and actual["expenses"] == 0:
            cursor = month_start - timedelta(days=1)
            continue

        partial = cash_flow(session, month_start, cutoff)
        remaining_income = Decimal("0")
        remaining_expenses = Decimal("0")
        for account in session.scalars(select(Account)).all():
            projection = _remaining_projection_for_account(session, account.id, cutoff, month_end)
            remaining_income += Decimal(projection["income"])
            remaining_expenses += Decimal(projection["expenses"])

        predicted_expenses = partial["expenses"] + remaining_expenses
        predicted_savings = partial["savings"] + remaining_income - remaining_expenses

        expense_abs_error += abs(predicted_expenses - actual["expenses"])
        expense_actual_total += actual["expenses"]
        savings_abs_error += abs(predicted_savings - actual["savings"])
        evaluated += 1
        cursor = month_start - timedelta(days=1)

    if evaluated == 0:
        return {
            "months_evaluated": 0,
            "expense_wape": None,
            "expense_accuracy": None,
            "savings_mae": None,
        }

    wape = None if expense_actual_total <= 0 else expense_abs_error / expense_actual_total
    accuracy = None if wape is None else max(Decimal("0"), Decimal("1") - wape)
    return {
        "months_evaluated": evaluated,
        "expense_wape": None if wape is None else str(wape.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "expense_accuracy": None if accuracy is None else str(accuracy.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "savings_mae": str(_money(savings_abs_error / Decimal(evaluated))),
    }


def month_end_projection(session: Session, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    start = as_of.replace(day=1)
    end = _month_end(as_of)
    actual = cash_flow(session, start, as_of)

    accounts = session.scalars(select(Account).order_by(Account.name)).all()
    account_rows = []
    remaining_income = Decimal("0")
    remaining_expenses = Decimal("0")

    for account in accounts:
        projection = _remaining_projection_for_account(session, account.id, as_of, end)
        projected_income = Decimal(projection["income"])
        projected_expenses = Decimal(projection["expenses"])
        projected_delta = projected_income - projected_expenses
        closing = account.current_balance + projected_delta
        remaining_income += projected_income
        remaining_expenses += projected_expenses
        account_rows.append({
            "id": account.id,
            "name": account.name,
            "institution_name": account.institution_name,
            "currency": account.currency,
            "current_balance": str(_money(account.current_balance)),
            "projected_remaining_income": str(_money(projected_income)),
            "projected_remaining_expenses": str(_money(projected_expenses)),
            "projected_change": str(_money(projected_delta)),
            "projected_closing_balance": str(_money(closing)),
            "method": projection["method"],
            "history_days": projection["history_days"],
        })

    commitments = _known_commitments(session, as_of + timedelta(days=1), end)
    # Commitments are not linked to a bank account in the current domain model.
    # Treat them as a floor for total remaining expenses, never distribute them
    # arbitrarily across accounts.
    total_remaining_expenses = max(remaining_expenses, commitments)
    commitment_adjustment = max(Decimal("0"), commitments - remaining_expenses)

    predicted_income = actual["income"] + remaining_income
    predicted_expenses = actual["expenses"] + total_remaining_expenses
    predicted_savings = predicted_income - predicted_expenses
    current_total_balance = sum((account.current_balance for account in accounts), Decimal("0"))
    projected_total_balance = current_total_balance + remaining_income - total_remaining_expenses

    accuracy = _backtest_accuracy(session, as_of)
    return {
        "as_of": str(as_of),
        "month_start": str(start),
        "month_end": str(end),
        "model_version": MODEL_VERSION,
        "actual_to_date": {
            "income": str(_money(actual["income"])),
            "expenses": str(_money(actual["expenses"])),
            "savings": str(_money(actual["savings"])),
        },
        "forecast_remaining": {
            "income": str(_money(remaining_income)),
            "expenses_from_history": str(_money(remaining_expenses)),
            "known_commitments": str(_money(commitments)),
            "commitment_floor_adjustment": str(_money(commitment_adjustment)),
            "expenses": str(_money(total_remaining_expenses)),
        },
        "projected_month_end": {
            "income": str(_money(predicted_income)),
            "expenses": str(_money(predicted_expenses)),
            "savings": str(_money(predicted_savings)),
            "total_balance": str(_money(projected_total_balance)),
        },
        "accuracy": accuracy,
        "accounts": account_rows,
        "notes": [
            "La proyección combina el mismo periodo del año anterior con el ritmo de los últimos 60 días cuando ambos existen.",
            "Los compromisos conocidos actúan como mínimo de gasto restante para no contarlos dos veces sobre el patrón histórico.",
            "Los compromisos no se reparten entre cuentas porque actualmente no tienen una cuenta bancaria asociada.",
            "Es una estimación basada en histórico y datos actuales, no un saldo garantizado.",
        ],
    }
