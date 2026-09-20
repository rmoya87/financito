from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Budget,Category,Transaction
from ..models_analytics import EntityLink

CENT=Decimal("0.01")
ESSENTIAL={"housing","groceries","utilities","telecom","insurance","health","education","family","pets","taxes","transport","vehicle","debt"}

def _refund_ids(session:Session,transaction_ids:list[str]|None=None)->set[str]:
    stmt=select(EntityLink.from_id).where(EntityLink.from_type=="transaction",EntityLink.relation_type=="refund_of")
    if transaction_ids:
        stmt=stmt.where(EntityLink.from_id.in_(transaction_ids))
    return set(session.scalars(stmt).all())

def cash_flow(session:Session,start:date,end:date)->dict:
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.is_internal_transfer.is_(False))).all()
    refunds=_refund_ids(session,[t.id for t in txs])
    income=Decimal("0");expenses=Decimal("0")
    for tx in txs:
        if tx.id in refunds and tx.amount>0:
            expenses-=tx.amount
        elif tx.amount>=0:
            income+=tx.amount
        else:
            expenses+=-tx.amount
    expenses=max(Decimal("0"),expenses)
    savings=income-expenses
    rate=None if income==0 else (savings/income).quantize(Decimal("0.0001"),rounding=ROUND_HALF_UP)
    return {"income":income.quantize(CENT),"expenses":expenses.quantize(CENT),"savings":savings.quantize(CENT),"savings_rate":rate}

def category_spending(session:Session,start:date,end:date)->list[dict]:
    categories={c.id:c for c in session.scalars(select(Category)).all()}
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.is_internal_transfer.is_(False))).all()
    refunds=_refund_ids(session,[t.id for t in txs]);totals=defaultdict(lambda:Decimal("0"))
    for tx in txs:
        if not tx.category_id:
            continue
        if tx.amount<0:
            totals[tx.category_id]+=-tx.amount
        elif tx.id in refunds:
            totals[tx.category_id]-=tx.amount
    rows=[]
    for cid,value in totals.items():
        if value<=0:continue
        c=categories.get(cid)
        rows.append({"category_id":cid,"category":c.name if c else "Sin categoría","system_key":c.system_key if c else "other","amount":value.quantize(CENT)})
    return sorted(rows,key=lambda x:x["amount"],reverse=True)

def merchant_spending(session:Session,start:date,end:date,limit:int=20)->list[dict]:
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.amount<0,Transaction.is_internal_transfer.is_(False))).all()
    totals=defaultdict(lambda:Decimal("0"))
    for tx in txs:
        name=tx.merchant_normalized or tx.merchant_raw or tx.description_normalized or tx.description_raw
        totals[name]+=-tx.amount
    return [{"merchant":k,"amount":v.quantize(CENT)} for k,v in sorted(totals.items(),key=lambda x:x[1],reverse=True)[:limit]]

def fixed_variable(session:Session,start:date,end:date)->dict:
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.amount<0,Transaction.is_internal_transfer.is_(False))).all()
    fixed=sum((-t.amount for t in txs if t.is_recurring),Decimal("0"))
    variable=sum((-t.amount for t in txs if not t.is_recurring),Decimal("0"))
    return {"fixed":fixed.quantize(CENT),"variable":variable.quantize(CENT)}

def essential_discretionary(session:Session,start:date,end:date)->dict:
    categories={c.id:c.system_key for c in session.scalars(select(Category)).all()}
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.amount<0,Transaction.is_internal_transfer.is_(False))).all()
    essential=discretionary=Decimal("0")
    for t in txs:
        if categories.get(t.category_id) in ESSENTIAL:essential+=-t.amount
        else:discretionary+=-t.amount
    return {"essential":essential.quantize(CENT),"discretionary":discretionary.quantize(CENT)}

def monthly_cashflow(session:Session,start:date,end:date)->list[dict]:
    txs=session.scalars(select(Transaction).where(Transaction.booking_date>=start,Transaction.booking_date<=end,Transaction.is_internal_transfer.is_(False))).all()
    refunds=_refund_ids(session,[t.id for t in txs]);buckets={}
    for tx in txs:
        key=tx.booking_date.strftime("%Y-%m")
        b=buckets.setdefault(key,{"income":Decimal("0"),"expenses":Decimal("0")})
        if tx.id in refunds and tx.amount>0:b["expenses"]-=tx.amount
        elif tx.amount>=0:b["income"]+=tx.amount
        else:b["expenses"]+=-tx.amount
    return [{"period":k,"income":str(max(Decimal("0"),v["income"]).quantize(CENT)),"expenses":str(max(Decimal("0"),v["expenses"]).quantize(CENT)),"savings":str((v["income"]-max(Decimal("0"),v["expenses"])).quantize(CENT))} for k,v in sorted(buckets.items())]

def budget_vs_actual(session:Session,start:date,end:date)->list[dict]:
    actual={x["category_id"]:x["amount"] for x in category_spending(session,start,end)}
    categories={c.id:c.name for c in session.scalars(select(Category)).all()}
    rows=[]
    for b in session.scalars(select(Budget)).all():
        a=actual.get(b.category_id,Decimal("0"))
        rows.append({"category_id":b.category_id,"category":categories.get(b.category_id,"Categoría"),"budget":str(b.amount),"actual":str(a),"variance":str((b.amount-a).quantize(CENT))})
    return rows

def overview(session:Session,start:date,end:date)->dict:
    flow=cash_flow(session,start,end)
    return {
        "period":{"start":start,"end":end},
        "cash_flow":{k:(str(v) if isinstance(v,Decimal) else v) for k,v in flow.items()},
        "by_category":[{**x,"amount":str(x["amount"])} for x in category_spending(session,start,end)],
        "by_merchant":[{**x,"amount":str(x["amount"])} for x in merchant_spending(session,start,end)],
        "fixed_variable":{k:str(v) for k,v in fixed_variable(session,start,end).items()},
        "essential_discretionary":{k:str(v) for k,v in essential_discretionary(session,start,end).items()},
        "monthly":monthly_cashflow(session,start,end),
        "budget_vs_actual":budget_vs_actual(session,start,end),
    }
