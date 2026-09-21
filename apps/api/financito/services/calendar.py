from __future__ import annotations

from calendar import monthrange
from datetime import date,timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category,Commitment,Contract,FinancialGoal,Transaction
from ..models_analytics import RecurringSeries


PREDICTABLE_CATEGORY_KEYS={
    "groceries","education","housing","utilities","telecom","insurance",
    "transport","vehicle","health","family","pets","subscriptions",
}


def _add_months(value:date,months:int)->date:
    index=value.year*12+(value.month-1)+months
    year,month_index=divmod(index,12)
    month=month_index+1
    day=min(value.day,monthrange(year,month)[1])
    return date(year,month,day)


def _advance(value:date,cadence:str)->date:
    if cadence=="weekly":return value+timedelta(days=7)
    if cadence=="monthly":return _add_months(value,1)
    if cadence=="quarterly":return _add_months(value,3)
    if cadence=="annual":return _add_months(value,12)
    return value+timedelta(days=30)


def _months_between(start:date,end:date):
    cursor=date(start.year,start.month,1)
    while cursor<=end:
        yield cursor
        cursor=_add_months(cursor,1)


def _category_pattern_events(session:Session,start:date,end:date)->list[dict]:
    history_end=start-timedelta(days=1)
    history_start=history_end-timedelta(days=365)
    categories={row.id:row for row in session.scalars(select(Category).where(Category.system_key.in_(PREDICTABLE_CATEGORY_KEYS))).all()}
    if not categories:
        return []
    rows=session.scalars(select(Transaction).where(
        Transaction.booking_date>=history_start,
        Transaction.booking_date<=history_end,
        Transaction.amount<0,
        Transaction.is_internal_transfer.is_(False),
        Transaction.is_extraordinary.is_(False),
        Transaction.category_id.in_(list(categories)),
    )).all()
    monthly={}
    for tx in rows:
        key=(tx.category_id,tx.booking_date.year,tx.booking_date.month)
        monthly[key]=monthly.get(key,Decimal("0"))+(-tx.amount)
    out=[]
    for category_id,category in categories.items():
        values=[amount for (cid,_,_),amount in monthly.items() if cid==category_id and amount>0]
        if len(values)<3:
            continue
        expected=Decimal(str(median(values)))
        if expected<=0:
            continue
        deviations=[abs(x-expected) for x in values]
        mad=Decimal(str(median(deviations))) if deviations else Decimal("0")
        variability=mad/expected if expected else Decimal("1")
        if variability<=Decimal("0.20"):confidence=Decimal("0.85")
        elif variability<=Decimal("0.40"):confidence=Decimal("0.75")
        elif variability<=Decimal("0.65"):confidence=Decimal("0.65")
        else:continue
        for month_start in _months_between(start,end):
            event_date=date(month_start.year,month_start.month,monthrange(month_start.year,month_start.month)[1])
            if event_date<start:event_date=start
            if event_date>end:continue
            out.append({
                "date":event_date,
                "type":"historical_pattern",
                "title":"Gasto esperado · "+category.name,
                "amount":str(expected.quantize(Decimal("0.01"))),
                "entity_id":"category:"+category_id+":"+month_start.isoformat(),
                "confidence":str(confidence),
                "basis":f"Mediana mensual de {len(values)} meses con histórico",
                "category":category.name,
            })
    return out


def events(session:Session,start:date,end:date)->list[dict]:
    out=[]
    for c in session.scalars(select(Commitment).where(Commitment.due_date>=start,Commitment.due_date<=end,Commitment.status=="active")).all():
        out.append({"date":c.due_date,"type":"commitment","title":c.title,"amount":str(c.amount),"entity_id":c.id,"confidence":str(c.confidence),"basis":"Compromiso conocido"})
    for c in session.scalars(select(Contract).where(Contract.renewal_date>=start,Contract.renewal_date<=end)).all():
        out.append({"date":c.renewal_date,"type":"renewal","title":"Renovación "+c.provider_name,"amount":None,"entity_id":c.id,"confidence":"1","basis":"Fecha contractual"})
    for g in session.scalars(select(FinancialGoal).where(FinancialGoal.target_date>=start,FinancialGoal.target_date<=end,FinancialGoal.status=="active")).all():
        out.append({"date":g.target_date,"type":"goal","title":g.name,"amount":str(g.target_amount),"entity_id":g.id,"confidence":"1","basis":"Objetivo registrado"})
    for r in session.scalars(select(RecurringSeries).where(RecurringSeries.status=="active")).all():
        occurrence=r.next_expected_date
        guard=0
        while occurrence<start and guard<60:
            occurrence=_advance(occurrence,r.cadence);guard+=1
        while occurrence<=end and guard<120:
            out.append({
                "date":occurrence,
                "type":"recurring",
                "title":r.merchant_normalized,
                "amount":str(r.expected_amount),
                "entity_id":r.id+":"+occurrence.isoformat(),
                "confidence":str(r.confidence),
                "basis":"Patrón recurrente detectado en movimientos",
            })
            occurrence=_advance(occurrence,r.cadence);guard+=1
    out.extend(_category_pattern_events(session,start,end))
    return sorted(out,key=lambda x:(x["date"],x["type"],x["title"]))
