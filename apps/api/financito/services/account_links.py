from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,Mortgage,Transaction
from ..models_analytics import EntityLink
from ..models_extended import InsurancePolicy,MortgagePaymentAllocation


def _single(values:set[str])->str|None:
    return next(iter(values)) if len(values)==1 else None


def synchronize_product_account_links(session:Session)->dict:
    """Infer missing account links only when payment evidence is unambiguous.

    Existing explicit account links are never changed automatically. A linked
    mortgage uses the selected bank account's institution as lender, making the
    account selection the stable identity source instead of stale document text.
    """
    mortgage_inferred=insurance_inferred=lenders_corrected=0

    mortgages=session.scalars(select(Mortgage)).all()
    for mortgage in mortgages:
        if mortgage.account_id is None:
            allocations=session.scalars(select(MortgagePaymentAllocation).where(
                MortgagePaymentAllocation.mortgage_id==mortgage.id
            )).all()
            tx_ids=[row.transaction_id for row in allocations]
            accounts=set()
            if tx_ids:
                accounts=set(session.scalars(select(Transaction.account_id).where(
                    Transaction.id.in_(tx_ids)
                )).all())
            account_id=_single(accounts)
            if account_id:
                mortgage.account_id=account_id
                mortgage_inferred+=1
        if mortgage.account_id:
            account=session.get(Account,mortgage.account_id)
            if account is not None and account.institution_name and mortgage.lender!=account.institution_name:
                mortgage.lender=account.institution_name[:180]
                lenders_corrected+=1

    policies=session.scalars(select(InsurancePolicy)).all()
    for policy in policies:
        if policy.account_id is not None:
            continue
        links=session.scalars(select(EntityLink).where(
            EntityLink.from_type=="transaction",
            EntityLink.relation_type=="payment_for",
            EntityLink.to_type=="insurance_policy",
            EntityLink.to_id==policy.id,
        )).all()
        tx_ids=[row.from_id for row in links]
        accounts=set()
        if tx_ids:
            accounts=set(session.scalars(select(Transaction.account_id).where(
                Transaction.id.in_(tx_ids)
            )).all())
        account_id=_single(accounts)
        if account_id:
            policy.account_id=account_id
            insurance_inferred+=1

    session.flush()
    return {
        "mortgage_accounts_inferred":mortgage_inferred,
        "insurance_accounts_inferred":insurance_inferred,
        "mortgage_lenders_corrected":lenders_corrected,
    }


def validate_account(session:Session,account_id:str|None)->Account|None:
    if not account_id:
        return None
    account=session.get(Account,account_id)
    if account is None:
        raise LookupError("Account not found")
    return account
