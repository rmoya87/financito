from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Budget, Category, Transaction
from ..models_analytics import EntityLink

CENT = Decimal("0.01")
ESSENTIAL = {
    "housing","groceries","utilities","telecom","insurance","health","education",
    "family","pets","taxes","transport","vehicle","debt",
}


def _categories(session: Session) -> dict[str, Category]:
    return {c.id: c for c in session.scalars(select(Category)).all()}


def _refund_links(session: Session, transaction_ids: list[str] | None = None) -> dict[str, str]:
    stmt = select(EntityLink).where(
        EntityLink.from_type == "transaction",
        EntityLink.relation_type == "refund_of",
        EntityLink.to_type == "transaction",
    )
    if transaction_ids:
        stmt = stmt.where(EntityLink.from_id.in_(transaction_ids))
    return {r.from_id: r.to_id for r in session.scalars(stmt).all()}


def _is_internal(tx: Transaction, categories: dict[str, Category]) -> bool:
    category = categories.get(tx.category_id or "")
    # When a category exists it is the accounting source of truth. This avoids
    # a stale legacy boolean excluding a positive Nómina/Ingreso after
    # recategorization. The boolean is only a fallback for uncategorized legacy
    # rows.
    if category is not None:
        return category.system_key == "internal_transfer"
    return tx.is_internal_transfer


def _is_refund(tx: Transaction, categories: dict[str, Category], refund_ids: set[str]) -> bool:
    category = categories.get(tx.category_id or "")
    return (
        tx.amount > 0
        and (tx.id in refund_ids or (category is not None and category.system_key == "refunds"))
    )


def _period_transactions(session: Session, start: date, end: date) -> tuple[list[Transaction], dict[str, Category]]:
    categories = _categories(session)
    rows = session.scalars(
        select(Transaction).where(
            Transaction.booking_date >= start,
            Transaction.booking_date <= end,
        )
    ).all()
    return [tx for tx in rows if not _is_internal(tx, categories)], categories


def cash_flow(session: Session, start: date, end: date) -> dict:
    txs, categories = _period_transactions(session, start, end)
    refund_links = _refund_links(session, [t.id for t in txs])
    refund_ids = set(refund_links)
    income = Decimal("0")
    expenses = Decimal("0")
    for tx in txs:
        if _is_refund(tx, categories, refund_ids):
            expenses -= tx.amount
        elif tx.amount >= 0:
            income += tx.amount
        else:
            expenses += -tx.amount
    expenses = max(Decimal("0"), expenses)
    savings = income - expenses
    rate = None if income == 0 else (savings / income).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    return {
        "income": income.quantize(CENT),
        "expenses": expenses.quantize(CENT),
        "savings": savings.quantize(CENT),
        "savings_rate": rate,
    }


def category_spending(session: Session, start: date, end: date) -> list[dict]:
    txs, categories = _period_transactions(session, start, end)
    refund_links = _refund_links(session, [t.id for t in txs])
    refund_ids = set(refund_links)
    by_id = {t.id: t for t in txs}
    totals = defaultdict(lambda: Decimal("0"))

    for tx in txs:
        if tx.amount < 0 and tx.category_id:
            totals[tx.category_id] += -tx.amount
        elif _is_refund(tx, categories, refund_ids):
            # If the original purchase is known, reduce that purchase category.
            # Otherwise the refund still reduces total expenses in cash_flow but
            # is not falsely displayed as positive spending.
            original = by_id.get(refund_links.get(tx.id, ""))
            if original and original.category_id:
                totals[original.category_id] -= tx.amount

    rows = []
    for category_id, value in totals.items():
        if value <= 0:
            continue
        category = categories.get(category_id)
        rows.append({
            "category_id": category_id,
            "category": category.name if category else "Sin categoría",
            "system_key": category.system_key if category else "other",
            "amount": value.quantize(CENT),
        })
    return sorted(rows, key=lambda x: x["amount"], reverse=True)


def merchant_spending(session: Session, start: date, end: date, limit: int = 20) -> list[dict]:
    txs, categories = _period_transactions(session, start, end)
    totals = defaultdict(lambda: Decimal("0"))
    for tx in txs:
        if tx.amount >= 0:
            continue
        name = (
            tx.merchant_normalized
            or tx.merchant_raw
            or tx.description_normalized
            or tx.description_raw
        )
        totals[name] += -tx.amount
    return [
        {"merchant": key, "amount": value.quantize(CENT)}
        for key, value in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def fixed_variable(session: Session, start: date, end: date) -> dict:
    txs, _ = _period_transactions(session, start, end)
    expenses = [t for t in txs if t.amount < 0]
    fixed = sum((-t.amount for t in expenses if t.is_recurring), Decimal("0"))
    variable = sum((-t.amount for t in expenses if not t.is_recurring), Decimal("0"))
    return {"fixed": fixed.quantize(CENT), "variable": variable.quantize(CENT)}


def essential_discretionary(session: Session, start: date, end: date) -> dict:
    txs, categories = _period_transactions(session, start, end)
    essential = Decimal("0")
    discretionary = Decimal("0")
    for tx in txs:
        if tx.amount >= 0:
            continue
        category = categories.get(tx.category_id or "")
        if category and category.system_key in ESSENTIAL:
            essential += -tx.amount
        else:
            discretionary += -tx.amount
    return {
        "essential": essential.quantize(CENT),
        "discretionary": discretionary.quantize(CENT),
    }


def monthly_cashflow(session: Session, start: date, end: date) -> list[dict]:
    txs, categories = _period_transactions(session, start, end)
    refund_ids = set(_refund_links(session, [t.id for t in txs]))
    buckets: dict[str, dict[str, Decimal]] = {}
    for tx in txs:
        key = tx.booking_date.strftime("%Y-%m")
        bucket = buckets.setdefault(key, {"income": Decimal("0"), "expenses": Decimal("0")})
        if _is_refund(tx, categories, refund_ids):
            bucket["expenses"] -= tx.amount
        elif tx.amount >= 0:
            bucket["income"] += tx.amount
        else:
            bucket["expenses"] += -tx.amount
    return [
        {
            "period": key,
            "income": str(max(Decimal("0"), values["income"]).quantize(CENT)),
            "expenses": str(max(Decimal("0"), values["expenses"]).quantize(CENT)),
            "savings": str(
                (values["income"] - max(Decimal("0"), values["expenses"])).quantize(CENT)
            ),
        }
        for key, values in sorted(buckets.items())
    ]


def budget_vs_actual(session: Session, start: date, end: date) -> list[dict]:
    actual = {x["category_id"]: x["amount"] for x in category_spending(session, start, end)}
    categories = {c.id: c.name for c in session.scalars(select(Category)).all()}
    rows = []
    for budget in session.scalars(select(Budget)).all():
        amount = actual.get(budget.category_id, Decimal("0"))
        rows.append({
            "category_id": budget.category_id,
            "category": categories.get(budget.category_id, "Categoría"),
            "budget": str(budget.amount),
            "actual": str(amount),
            "variance": str((budget.amount - amount).quantize(CENT)),
        })
    return rows


def overview(session: Session, start: date, end: date) -> dict:
    flow = cash_flow(session, start, end)
    return {
        "period": {"start": start, "end": end},
        "cash_flow": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in flow.items()},
        "by_category": [{**x, "amount": str(x["amount"])} for x in category_spending(session, start, end)],
        "by_merchant": [{**x, "amount": str(x["amount"])} for x in merchant_spending(session, start, end)],
        "fixed_variable": {k: str(v) for k, v in fixed_variable(session, start, end).items()},
        "essential_discretionary": {
            k: str(v) for k, v in essential_discretionary(session, start, end).items()
        },
        "monthly": monthly_cashflow(session, start, end),
        "budget_vs_actual": budget_vs_actual(session, start, end),
    }
