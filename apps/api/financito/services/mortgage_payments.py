from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Mortgage, Transaction
from ..models_extended import MortgagePaymentAllocation
from .snapshots import record_snapshot

_CENT=Decimal("0.01")


def _money(value:Decimal)->Decimal:
    return Decimal(value).quantize(_CENT,rounding=ROUND_HALF_UP)


def reconcile_manual_balance(session:Session,mortgage_id:str)->int:
    rows=session.scalars(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.mortgage_id==mortgage_id,
        MortgagePaymentAllocation.applied_to_balance.is_(True),
    )).all()
    for row in rows:
        row.applied_to_balance=False
    return len(rows)


def link_payment(session:Session,transaction_id:str,mortgage_id:str)->MortgagePaymentAllocation:
    tx=session.get(Transaction,transaction_id)
    mortgage=session.get(Mortgage,mortgage_id)
    if tx is None:
        raise LookupError("Transaction not found")
    if mortgage is None:
        raise LookupError("Mortgage not found")
    if tx.is_internal_transfer or tx.amount>=0:
        raise ValueError("Solo se pueden vincular cargos de gasto a una hipoteca")

    existing=session.scalar(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.transaction_id==transaction_id
    ))
    if existing is not None:
        if existing.mortgage_id==mortgage_id:
            return existing
        unlink_payment(session,transaction_id)
        mortgage=session.get(Mortgage,mortgage_id)
        if mortgage is None:
            raise LookupError("Mortgage not found")

    payment=_money(abs(tx.amount))
    balance_before=_money(max(Decimal("0"),mortgage.remaining_principal))
    rate=max(Decimal("0"),mortgage.nominal_rate)
    estimated_interest=_money(balance_before*rate/Decimal("12"))
    interest=_money(min(payment,estimated_interest))
    principal=_money(min(balance_before,max(Decimal("0"),payment-interest)))
    balance_after=_money(max(Decimal("0"),balance_before-principal))

    row=MortgagePaymentAllocation(
        mortgage_id=mortgage_id,
        transaction_id=transaction_id,
        payment_amount=payment,
        principal_amount=principal,
        interest_amount=interest,
        currency=tx.currency,
        balance_before=balance_before,
        balance_after=balance_after,
        applied_to_balance=True,
        calculation_method="estimated_nominal_monthly_rate",
    )
    session.add(row)
    mortgage.remaining_principal=balance_after
    session.flush()
    record_snapshot(session,"mortgage",mortgage.id,{
        "remaining_principal":str(mortgage.remaining_principal),
        "nominal_rate":str(mortgage.nominal_rate),
        "monthly_payment":str(mortgage.monthly_payment),
        "remaining_months":mortgage.remaining_months,
        "currency":mortgage.currency,
        "linked_transaction_id":transaction_id,
        "principal_component":str(principal),
        "interest_component":str(interest),
    },as_of=tx.booking_date,source="mortgage_payment_linked")
    return row


def unlink_payment(session:Session,transaction_id:str)->MortgagePaymentAllocation|None:
    row=session.scalar(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.transaction_id==transaction_id
    ))
    if row is None:
        return None
    mortgage=session.get(Mortgage,row.mortgage_id)
    if mortgage is not None and row.applied_to_balance:
        mortgage.remaining_principal=_money(max(Decimal("0"),mortgage.remaining_principal)+row.principal_amount)
        session.flush()
        tx=session.get(Transaction,transaction_id)
        record_snapshot(session,"mortgage",mortgage.id,{
            "remaining_principal":str(mortgage.remaining_principal),
            "nominal_rate":str(mortgage.nominal_rate),
            "monthly_payment":str(mortgage.monthly_payment),
            "remaining_months":mortgage.remaining_months,
            "currency":mortgage.currency,
            "unlinked_transaction_id":transaction_id,
            "restored_principal":str(row.principal_amount),
        },as_of=None if tx is None else tx.booking_date,source="mortgage_payment_unlinked")
    session.delete(row)
    session.flush()
    return row


def payment_rows(session:Session,mortgage_id:str)->list[dict]:
    allocations=session.scalars(select(MortgagePaymentAllocation).where(
        MortgagePaymentAllocation.mortgage_id==mortgage_id
    )).all()
    if not allocations:
        return []
    tx_ids=[row.transaction_id for row in allocations]
    transactions={row.id:row for row in session.scalars(select(Transaction).where(Transaction.id.in_(tx_ids))).all()}
    account_ids={tx.account_id for tx in transactions.values()}
    accounts={} if not account_ids else {
        row.id:row for row in session.scalars(select(Account).where(Account.id.in_(account_ids))).all()
    }
    items=[]
    for allocation in allocations:
        tx=transactions.get(allocation.transaction_id)
        if tx is None:
            continue
        account=accounts.get(tx.account_id)
        items.append({
            "id":allocation.id,
            "transaction_id":tx.id,
            "booking_date":str(tx.booking_date),
            "description":tx.description_raw,
            "merchant":tx.merchant_raw,
            "payment_amount":str(_money(allocation.payment_amount)),
            "principal_amount":str(_money(allocation.principal_amount)),
            "interest_amount":str(_money(allocation.interest_amount)),
            "currency":allocation.currency,
            "balance_before":str(_money(allocation.balance_before)),
            "balance_after":str(_money(allocation.balance_after)),
            "applied_to_balance":allocation.applied_to_balance,
            "calculation_method":allocation.calculation_method,
            "account_id":tx.account_id,
            "account_name":None if account is None else account.name,
            "institution_name":None if account is None else account.institution_name,
        })
    items.sort(key=lambda item:(item["booking_date"],item["id"]),reverse=True)
    return items
