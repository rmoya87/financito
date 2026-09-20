from __future__ import annotations
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Account,Mortgage,Portfolio,Position
from ..models_extended import Asset,Liability
Q=Decimal("0.01")
def m(v):return Decimal(v).quantize(Q,rounding=ROUND_HALF_UP)
def summary(session:Session)->dict:
    accounts=sum((a.current_balance for a in session.scalars(select(Account)).all()),Decimal("0"))
    assets_rows=session.scalars(select(Asset)).all();assets=sum((a.current_value*a.ownership_percentage/Decimal("100") for a in assets_rows),Decimal("0"))
    liabilities_rows=session.scalars(select(Liability)).all();liabilities=sum((l.outstanding_amount*l.ownership_percentage/Decimal("100") for l in liabilities_rows),Decimal("0"))
    mortgages=sum((x.remaining_principal for x in session.scalars(select(Mortgage)).all()),Decimal("0"))
    positions=session.scalars(select(Position)).all();investments=sum((p.quantity*(p.current_price or p.average_cost) for p in positions),Decimal("0"))
    gross=accounts+assets+investments;debt=liabilities+mortgages
    return {"accounts":str(m(accounts)),"manual_assets":str(m(assets)),"investments":str(m(investments)),"liabilities":str(m(liabilities)),"mortgages":str(m(mortgages)),"gross_assets":str(m(gross)),"total_debt":str(m(debt)),"net_worth":str(m(gross-debt))}
