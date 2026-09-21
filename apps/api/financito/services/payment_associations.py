from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..models import Mortgage,Transaction
from ..models_analytics import EntityLink,ProductPaymentRule
from ..models_extended import InsurancePolicy,MortgagePaymentAllocation
from .categorization import normalize_text
from .mortgage_payments import link_payment as link_mortgage_payment,unlink_payment as unlink_mortgage_payment


def _concept(tx:Transaction)->str:
    return normalize_text(tx.description_raw)


def _validate_expense(tx:Transaction)->None:
    if tx.is_internal_transfer or tx.amount>=0:
        raise ValueError("Solo se pueden asociar cargos de gasto a una hipoteca o seguro")
    if not _concept(tx):
        raise ValueError("El movimiento no tiene un concepto utilizable para crear una regla automática")


def _remove_insurance_link(session:Session,transaction_id:str)->int:
    return session.execute(delete(EntityLink).where(
        EntityLink.from_type=="transaction",
        EntityLink.from_id==transaction_id,
        EntityLink.relation_type=="payment_for",
        EntityLink.to_type=="insurance_policy",
    )).rowcount or 0


def _set_insurance_link(session:Session,tx:Transaction,policy_id:str,source_type:str,source_ref:str)->bool:
    policy=session.get(InsurancePolicy,policy_id)
    if policy is None:
        return False
    existing_mortgage=session.scalar(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.transaction_id==tx.id
    ))
    if existing_mortgage is not None:
        unlink_mortgage_payment(session,tx.id)
    _remove_insurance_link(session,tx.id)
    session.add(EntityLink(
        from_type="transaction",from_id=tx.id,relation_type="payment_for",
        to_type="insurance_policy",to_id=policy_id,confidence=Decimal("1"),
        source_type=source_type,source_ref=source_ref,
    ))
    session.flush()
    return True


def _set_mortgage_link(
    session:Session,tx:Transaction,mortgage_id:str,apply_to_balance:bool
)->bool:
    mortgage=session.get(Mortgage,mortgage_id)
    if mortgage is None:
        return False
    _remove_insurance_link(session,tx.id)
    existing=session.scalar(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.transaction_id==tx.id
    ))
    # Never demote a payment that was already applied to the same mortgage.
    if (
        existing is not None
        and existing.mortgage_id==mortgage_id
        and existing.applied_to_balance
        and not apply_to_balance
    ):
        return True
    link_mortgage_payment(session,tx.id,mortgage_id,apply_to_balance=apply_to_balance)
    return True


def _target_exists(session:Session,target_type:str,target_id:str)->bool:
    if target_type=="insurance_policy":
        return session.get(InsurancePolicy,target_id) is not None
    if target_type=="mortgage":
        return session.get(Mortgage,target_id) is not None
    return False


def learn_and_apply_payment_rule(
    session:Session,
    source_transaction_id:str,
    target_type:str,
    target_id:str,
)->dict:
    source=session.get(Transaction,source_transaction_id)
    if source is None:
        raise LookupError("Transaction not found")
    _validate_expense(source)
    if target_type not in {"insurance_policy","mortgage"}:
        raise ValueError("Unsupported payment rule target")
    if not _target_exists(session,target_type,target_id):
        raise LookupError("Payment target not found")

    concept=_concept(source)
    rule=session.scalar(select(ProductPaymentRule).where(
        ProductPaymentRule.matcher_type=="description_exact",
        ProductPaymentRule.matcher_value==concept,
    ))
    if rule is None:
        rule=ProductPaymentRule(
            matcher_type="description_exact",
            matcher_value=concept,
            target_type=target_type,
            target_id=target_id,
            enabled=True,
            source_transaction_id=source.id,
        )
        session.add(rule)
        session.flush()
    else:
        rule.target_type=target_type
        rule.target_id=target_id
        rule.enabled=True
        rule.source_transaction_id=source.id
        session.flush()

    rows=session.scalars(select(Transaction).where(
        Transaction.description_normalized==concept,
        Transaction.amount<0,
        Transaction.is_internal_transfer.is_(False),
    ).order_by(Transaction.booking_date,Transaction.id)).all()

    linked=0
    historical=0
    for tx in rows:
        if target_type=="insurance_policy":
            ok=_set_insurance_link(
                session,tx,target_id,
                "user_payment_rule" if tx.id==source.id else "payment_rule",
                rule.id,
            )
        else:
            apply_to_balance=tx.id==source.id
            ok=_set_mortgage_link(session,tx,target_id,apply_to_balance)
            if ok and not apply_to_balance:
                historical+=1
        if ok:
            linked+=1

    session.flush()
    return {
        "rule_id":rule.id,
        "matcher_type":rule.matcher_type,
        "matcher_value":rule.matcher_value,
        "target_type":target_type,
        "target_id":target_id,
        "linked_transactions":linked,
        "historical_transactions":historical,
        "future_automatic":True,
    }


def apply_payment_rule_to_transaction(session:Session,tx:Transaction)->dict|None:
    if tx.amount>=0 or tx.is_internal_transfer:
        return None
    concept=_concept(tx)
    if not concept:
        return None
    rule=session.scalar(select(ProductPaymentRule).where(
        ProductPaymentRule.matcher_type=="description_exact",
        ProductPaymentRule.matcher_value==concept,
        ProductPaymentRule.enabled.is_(True),
    ))
    if rule is None:
        return None
    if not _target_exists(session,rule.target_type,rule.target_id):
        rule.enabled=False
        session.flush()
        return {"rule_id":rule.id,"applied":False,"reason":"target_missing"}

    if rule.target_type=="insurance_policy":
        applied=_set_insurance_link(session,tx,rule.target_id,"payment_rule",rule.id)
        apply_to_balance=False
    elif rule.target_type=="mortgage":
        # A historical backfill predating the learned rule is associated for
        # traceability but must not reduce an already-current manual balance.
        apply_to_balance=tx.booking_date>=rule.created_at.date()
        applied=_set_mortgage_link(session,tx,rule.target_id,apply_to_balance)
    else:
        rule.enabled=False
        session.flush()
        return {"rule_id":rule.id,"applied":False,"reason":"unsupported_target"}

    session.flush()
    return {
        "rule_id":rule.id,
        "applied":bool(applied),
        "target_type":rule.target_type,
        "target_id":rule.target_id,
        "apply_to_balance":apply_to_balance,
    }


def payment_rule_for_transaction(session:Session,tx:Transaction)->ProductPaymentRule|None:
    concept=_concept(tx)
    if not concept:
        return None
    return session.scalar(select(ProductPaymentRule).where(
        ProductPaymentRule.matcher_type=="description_exact",
        ProductPaymentRule.matcher_value==concept,
        ProductPaymentRule.enabled.is_(True),
    ))
