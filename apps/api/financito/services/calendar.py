from __future__ import annotations

from calendar import monthrange
from datetime import date,timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,Category,Commitment,Contract,FinancialGoal,Transaction
from ..models_analytics import RecurringPreference,RecurringSeries
from ..domain.analytics import recurring_is_current


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


def _category_pattern_events(session:Session,start:date,end:date,account_id:str|None=None,account_type:str|None=None)->list[dict]:
    history_end=start-timedelta(days=1)
    history_start=history_end-timedelta(days=365)
    categories={row.id:row for row in session.scalars(select(Category).where(Category.system_key.in_(PREDICTABLE_CATEGORY_KEYS))).all()}
    if not categories:
        return []
    stmt=select(Transaction).where(
        Transaction.booking_date>=history_start,
        Transaction.booking_date<=history_end,
        Transaction.amount<0,
        Transaction.is_internal_transfer.is_(False),
        Transaction.is_extraordinary.is_(False),
        Transaction.category_id.in_(list(categories)),
    )
    if account_id:stmt=stmt.where(Transaction.account_id==account_id)
    elif account_type:stmt=stmt.where(Transaction.account_id.in_(select(Account.id).where(Account.account_type==account_type)))
    rows=session.scalars(stmt).all()
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
            days_in_month=monthrange(month_start.year,month_start.month)[1]
            month_end=date(month_start.year,month_start.month,days_in_month)
            period_start=max(start,month_start)
            period_end=min(end,month_end)
            if period_start>period_end:continue
            covered_days=(period_end-period_start).days+1
            factor=Decimal(covered_days)/Decimal(days_in_month)
            projected=(expected*factor).quantize(Decimal("0.01"))
            basis=f"Mediana mensual de {len(values)} meses con histórico"
            if covered_days<days_in_month:
                basis+=f", ajustada a {covered_days} de {days_in_month} días"
            out.append({
                "date":period_end,
                "type":"historical_pattern",
                "title":"Gasto esperado · "+category.name,
                "amount":str(projected),
                "entity_id":"category:"+category_id+":"+month_start.isoformat(),
                "confidence":str(confidence),
                "basis":basis,
                "category":category.name,
            })
    return out


def events(session:Session,start:date,end:date,account_id:str|None=None,account_type:str|None=None)->list[dict]:
    out=[]
    scope_ids=None
    if account_id:scope_ids={account_id}
    elif account_type:scope_ids=set(session.scalars(select(Account.id).where(Account.account_type==account_type)).all())
    commitment_stmt=select(Commitment).where(Commitment.status=="active",Commitment.due_date<=end)
    if scope_ids is not None:commitment_stmt=commitment_stmt.where(Commitment.account_id.in_(scope_ids))
    for c in session.scalars(commitment_stmt).all():
        occurrence=c.due_date;guard=0
        while c.recurrence and occurrence<start and guard<120:
            occurrence=_advance(occurrence,c.recurrence);guard+=1
        if not c.recurrence:
            if start<=occurrence<=end:
                out.append({"date":occurrence,"type":"commitment","title":c.title,"amount":str(c.amount),"entity_id":c.id,"confidence":str(c.confidence),"basis":"Compromiso conocido"})
            continue
        while occurrence<=end and guard<240:
            if occurrence>=start:
                out.append({"date":occurrence,"type":"commitment","title":c.title,"amount":str(c.amount),"entity_id":c.id+":"+occurrence.isoformat(),"confidence":str(c.confidence),"basis":"Compromiso conocido · "+c.recurrence})
            occurrence=_advance(occurrence,c.recurrence);guard+=1
    for c in session.scalars(select(Contract).where(Contract.renewal_date>=start,Contract.renewal_date<=end)).all():
        out.append({"date":c.renewal_date,"type":"renewal","title":"Renovación "+c.provider_name,"amount":None,"entity_id":c.id,"confidence":"1","basis":"Fecha contractual"})
    goal_stmt=select(FinancialGoal).where(FinancialGoal.target_date>=start,FinancialGoal.target_date<=end,FinancialGoal.status=="active")
    if scope_ids is not None:goal_stmt=goal_stmt.where(FinancialGoal.account_id.in_(scope_ids))
    for g in session.scalars(goal_stmt).all():
        out.append({"date":g.target_date,"type":"goal","title":g.name,"amount":str(g.target_amount),"entity_id":g.id,"confidence":"1","basis":"Objetivo registrado"})
    prefs={p.merchant_key:p for p in session.scalars(select(RecurringPreference)).all()}
    scoped_merchants=None
    if scope_ids is not None:
        scoped_merchants=set(x for x in session.scalars(select(Transaction.merchant_normalized).where(
            Transaction.account_id.in_(scope_ids),Transaction.merchant_normalized.is_not(None)
        )).all() if x)
    for r in session.scalars(select(RecurringSeries).where(RecurringSeries.status=="active")).all():
        if not recurring_is_current(r):continue
        if scoped_merchants is not None and r.merchant_normalized not in scoped_merchants:continue
        pref=prefs.get(r.merchant_normalized.strip().lower())
        if pref and pref.action=="not_subscription":continue
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
    out.extend(_category_pattern_events(session,start,end,account_id,account_type))
    return sorted(out,key=lambda x:(x["date"],x["type"],x["title"]))
