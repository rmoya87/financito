from __future__ import annotations
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Account,Mortgage,Portfolio,Position
from ..models_extended import Asset,Liability

Q=Decimal("0.01")
def m(v):return Decimal(v).quantize(Q,rounding=ROUND_HALF_UP)

def _account_ids(session:Session,account_id:str|None=None,account_type:str|None=None)->set[str]|None:
    if account_id:
        return {account_id}
    if account_type:
        return set(session.scalars(select(Account.id).where(Account.account_type==account_type)).all())
    return None

def summary(session:Session,account_id:str|None=None,account_type:str|None=None)->dict:
    scope=_account_ids(session,account_id,account_type)
    account_stmt=select(Account)
    if scope is not None:
        account_stmt=account_stmt.where(Account.id.in_(scope))
    accounts=sum((a.current_balance for a in session.scalars(account_stmt).all()),Decimal("0"))

    # Physical/manual assets and non-mortgage liabilities are household-level
    # wealth and remain visible regardless of the bank-account filter.
    assets_rows=session.scalars(select(Asset)).all()
    assets=sum((a.current_value*a.ownership_percentage/Decimal("100") for a in assets_rows),Decimal("0"))
    liabilities_rows=session.scalars(select(Liability)).all()
    liabilities=sum((l.outstanding_amount*l.ownership_percentage/Decimal("100") for l in liabilities_rows),Decimal("0"))

    mortgage_stmt=select(Mortgage)
    if scope is not None:
        mortgage_stmt=mortgage_stmt.where(Mortgage.account_id.in_(scope))
    mortgages=sum((x.remaining_principal for x in session.scalars(mortgage_stmt).all()),Decimal("0"))

    portfolio_stmt=select(Portfolio.id)
    if scope is not None:
        portfolio_stmt=portfolio_stmt.where(Portfolio.account_id.in_(scope))
    portfolio_ids=list(session.scalars(portfolio_stmt).all())
    positions=[] if not portfolio_ids else session.scalars(select(Position).where(Position.portfolio_id.in_(portfolio_ids))).all()
    investments=sum((p.quantity*(p.current_price or p.average_cost) for p in positions),Decimal("0"))

    gross=accounts+assets+investments
    debt=liabilities+mortgages
    return {
        "accounts":str(m(accounts)),
        "manual_assets":str(m(assets)),
        "investments":str(m(investments)),
        "liabilities":str(m(liabilities)),
        "mortgages":str(m(mortgages)),
        "gross_assets":str(m(gross)),
        "total_debt":str(m(debt)),
        "net_worth":str(m(gross-debt)),
    }
