from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Category, Transaction
from ..models_analytics import EntityLink, TransactionRule, TransactionSplit
from .categorization import ensure_categories, normalize_text


def category_system_key(session: Session, category_id: str | None) -> str | None:
    if not category_id:
        return None
    category = session.get(Category, category_id)
    return None if category is None else category.system_key


def apply_category_semantics(session: Session, tx: Transaction) -> str | None:
    """Synchronize accounting flags with the selected category.

    The category is the source of truth whenever one exists:
    - Movimiento entre cuentas => excluded from income/expense totals.
    - Any other category, including Nómina => not an internal transfer.
    - Reembolsos keeps its separate cash-flow treatment as a reduction of
      expense instead of artificial income.
    """
    key = category_system_key(session, tx.category_id)
    if key is not None:
        tx.is_internal_transfer = key == "internal_transfer"
    return key


def synchronize_transaction_semantics(session: Session) -> int:
    """Repair stale accounting flags left by older categorization flows."""
    categories = {c.id: c.system_key for c in session.scalars(select(Category)).all()}
    changed = 0
    for tx in session.scalars(select(Transaction).where(Transaction.category_id.is_not(None))).all():
        expected = categories.get(tx.category_id) == "internal_transfer"
        if tx.is_internal_transfer != expected:
            tx.is_internal_transfer = expected
            changed += 1
    session.flush()
    return changed


def pair_internal_transfer_counterpart(
    session: Session, tx: Transaction, window_days: int = 3
) -> str | None:
    """Pair an explicitly internal transfer with its opposite bank movement.

    Only a unique best candidate is changed. A counterpart that the user has
    explicitly verified as another category is never overwritten.
    """
    if category_system_key(session, tx.category_id) != "internal_transfer":
        return None

    start = tx.booking_date - timedelta(days=window_days)
    end = tx.booking_date + timedelta(days=window_days)
    candidates = session.scalars(
        select(Transaction).where(
            Transaction.id != tx.id,
            Transaction.account_id != tx.account_id,
            Transaction.currency == tx.currency,
            Transaction.amount == -tx.amount,
            Transaction.booking_date >= start,
            Transaction.booking_date <= end,
        )
    ).all()
    eligible = []
    for candidate in candidates:
        key = category_system_key(session, candidate.category_id)
        if candidate.user_verified and key != "internal_transfer":
            continue
        eligible.append(candidate)
    if not eligible:
        return None

    eligible.sort(key=lambda row: (abs((row.booking_date - tx.booking_date).days), row.id))
    best_gap = abs((eligible[0].booking_date - tx.booking_date).days)
    best = [row for row in eligible if abs((row.booking_date - tx.booking_date).days) == best_gap]
    if len(best) != 1:
        return None
    counterpart = best[0]

    categories = ensure_categories(session)
    counterpart.category_id = categories["internal_transfer"].id
    counterpart.is_internal_transfer = True
    if not counterpart.user_verified:
        counterpart.categorization_method = "internal_transfer_pair"
        counterpart.categorization_confidence = Decimal("0.99")

    tx.is_internal_transfer = True
    existing = session.scalar(
        select(EntityLink.id).where(
            EntityLink.from_type == "transaction",
            EntityLink.from_id == tx.id,
            EntityLink.relation_type == "internal_transfer_pair",
            EntityLink.to_type == "transaction",
            EntityLink.to_id == counterpart.id,
        )
    )
    reverse = session.scalar(
        select(EntityLink.id).where(
            EntityLink.from_type == "transaction",
            EntityLink.from_id == counterpart.id,
            EntityLink.relation_type == "internal_transfer_pair",
            EntityLink.to_type == "transaction",
            EntityLink.to_id == tx.id,
        )
    )
    if not existing and not reverse:
        session.add(
            EntityLink(
                from_type="transaction",
                from_id=tx.id,
                relation_type="internal_transfer_pair",
                to_type="transaction",
                to_id=counterpart.id,
                confidence=Decimal("1") if tx.user_verified else Decimal("0.99"),
                source_type="category_transfer_pair",
                source_ref=counterpart.id,
            )
        )
    session.flush()
    return counterpart.id


def apply_rule(session: Session, tx: Transaction) -> bool:
    if tx.user_verified:
        return False
    text = normalize_text((tx.merchant_raw or "") + " " + tx.description_raw)
    merchant = normalize_text(tx.merchant_raw or "")
    for rule in session.scalars(
        select(TransactionRule)
        .where(TransactionRule.enabled.is_(True))
        .order_by(TransactionRule.priority, TransactionRule.id)
    ).all():
        value = normalize_text(rule.matcher_value)
        matched = False
        if rule.matcher_type == "contains":
            matched = value in text
        elif rule.matcher_type == "merchant_exact":
            matched = value == merchant
        elif rule.matcher_type == "regex":
            try:
                matched = bool(re.search(rule.matcher_value, text, re.I))
            except re.error:
                matched = False
        if matched:
            tx.category_id = rule.category_id
            tx.categorization_method = "rule"
            tx.categorization_confidence = Decimal("1")
            key=apply_category_semantics(session, tx)
            if key=="internal_transfer":
                pair_internal_transfer_counterpart(session,tx)
            return True
    return False


def apply_rules_to_unverified(session: Session) -> int:
    changed = 0
    for tx in session.scalars(
        select(Transaction).where(Transaction.user_verified.is_(False))
    ).all():
        if apply_rule(session, tx):
            changed += 1
    session.flush()
    return changed


def detect_internal_transfers(session: Session) -> int:
    categories = ensure_categories(session)
    internal_category = categories["internal_transfer"]
    txs = session.scalars(
        select(Transaction)
        .where(Transaction.user_verified.is_(False))
        .order_by(Transaction.booking_date, Transaction.id)
    ).all()
    protected = {"salary", "refunds"}
    marked: set[str] = set()
    for i, left in enumerate(txs):
        if category_system_key(session, left.category_id) in protected:
            continue
        if left.id in marked:
            continue
        for right in txs[i + 1 :]:
            if right.booking_date > left.booking_date + timedelta(days=3):
                break
            if right.id in marked or right.account_id == left.account_id:
                continue
            if category_system_key(session, right.category_id) in protected:
                continue
            if left.currency != right.currency:
                continue
            if left.amount + right.amount == 0 and abs(
                (right.booking_date - left.booking_date).days
            ) <= 3:
                left.is_internal_transfer = True
                right.is_internal_transfer = True
                for tx in (left, right):
                    if not tx.user_verified:
                        tx.category_id = internal_category.id
                        tx.categorization_method = "internal_transfer_match"
                        tx.categorization_confidence = Decimal("0.99")
                existing = session.scalar(
                    select(EntityLink.id).where(
                        EntityLink.from_type == "transaction",
                        EntityLink.from_id == left.id,
                        EntityLink.relation_type == "internal_transfer_pair",
                        EntityLink.to_type == "transaction",
                        EntityLink.to_id == right.id,
                    )
                )
                if not existing:
                    session.add(
                        EntityLink(
                            from_type="transaction",
                            from_id=left.id,
                            relation_type="internal_transfer_pair",
                            to_type="transaction",
                            to_id=right.id,
                            confidence=Decimal("0.99"),
                            source_type="deterministic_transfer_match",
                            source_ref=right.id,
                        )
                    )
                marked.update([left.id, right.id])
                break
    session.flush()
    return len(marked) // 2


def set_splits(
    session: Session, transaction_id: str, splits: list[dict]
) -> list[TransactionSplit]:
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise ValueError("Transaction not found")
    total = sum((Decimal(str(x["amount"])) for x in splits), Decimal("0"))
    if total != abs(tx.amount):
        raise ValueError("Split total must exactly match absolute transaction amount")
    for item in splits:
        if Decimal(str(item["amount"])) <= 0:
            raise ValueError("Split amounts must be positive")
        if not session.get(Category, item["category_id"]):
            raise ValueError("Category not found")
    session.execute(
        delete(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    )
    rows = [
        TransactionSplit(
            transaction_id=transaction_id,
            amount=Decimal(str(x["amount"])),
            category_id=x["category_id"],
            note=x.get("note"),
        )
        for x in splits
    ]
    session.add_all(rows)
    session.flush()
    return rows


def _refund_match(
    session: Session, refund: Transaction, negatives: list[Transaction], lookback_days: int
) -> Transaction | None:
    merchant = refund.merchant_normalized or normalize_text(refund.merchant_raw or "")
    if not merchant:
        return None
    matches = [
        expense
        for expense in negatives
        if (expense.merchant_normalized or normalize_text(expense.merchant_raw or ""))
        == merchant
        and expense.booking_date <= refund.booking_date
        and (refund.booking_date - expense.booking_date).days <= lookback_days
        and abs((-expense.amount) - refund.amount) <= Decimal("0.01")
    ]
    return max(matches, key=lambda x: x.booking_date) if matches else None


def detect_refunds(session: Session, lookback_days: int = 90) -> int:
    categories = ensure_categories(session)
    refund_category = categories["refunds"]
    positives = session.scalars(
        select(Transaction)
        .where(Transaction.amount > 0, Transaction.is_internal_transfer.is_(False))
        .order_by(Transaction.booking_date)
    ).all()
    negatives = session.scalars(
        select(Transaction)
        .where(Transaction.amount < 0, Transaction.is_internal_transfer.is_(False))
        .order_by(Transaction.booking_date)
    ).all()
    created = 0
    for refund in positives:
        existing = session.scalar(
            select(EntityLink.id).where(
                EntityLink.from_type == "transaction",
                EntityLink.from_id == refund.id,
                EntityLink.relation_type == "refund_of",
            )
        )
        if existing:
            # Keep the accounting category explicit even for links created by
            # older versions that copied the original expense category.
            if not refund.user_verified:
                refund.category_id = refund_category.id
                refund.categorization_method = "refund_match"
                refund.categorization_confidence = Decimal("0.98")
            continue
        expense = _refund_match(session, refund, negatives, lookback_days)
        if expense is None:
            continue
        session.add(
            EntityLink(
                from_type="transaction",
                from_id=refund.id,
                relation_type="refund_of",
                to_type="transaction",
                to_id=expense.id,
                confidence=Decimal("0.98"),
                source_type="deterministic_refund_match",
                source_ref=expense.id,
            )
        )
        if not refund.user_verified:
            refund.category_id = refund_category.id
            refund.categorization_method = "refund_match"
            refund.categorization_confidence = Decimal("0.98")
        created += 1
    session.flush()
    return created
