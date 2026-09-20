from __future__ import annotations
from datetime import date,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Commitment,Contract,FinancialGoal
from ..models_analytics import RecurringSeries
def events(session:Session,start:date,end:date)->list[dict]:
    out=[]
    for c in session.scalars(select(Commitment).where(Commitment.due_date>=start,Commitment.due_date<=end,Commitment.status=="active")).all():out.append({"date":c.due_date,"type":"commitment","title":c.title,"amount":str(c.amount),"entity_id":c.id})
    for c in session.scalars(select(Contract).where(Contract.renewal_date>=start,Contract.renewal_date<=end)).all():out.append({"date":c.renewal_date,"type":"renewal","title":"Renovación "+c.provider_name,"amount":None,"entity_id":c.id})
    for g in session.scalars(select(FinancialGoal).where(FinancialGoal.target_date>=start,FinancialGoal.target_date<=end,FinancialGoal.status=="active")).all():out.append({"date":g.target_date,"type":"goal","title":g.name,"amount":str(g.target_amount),"entity_id":g.id})
    for r in session.scalars(select(RecurringSeries).where(RecurringSeries.next_expected_date>=start,RecurringSeries.next_expected_date<=end,RecurringSeries.status=="active")).all():out.append({"date":r.next_expected_date,"type":"recurring","title":r.merchant_normalized,"amount":str(r.expected_amount),"entity_id":r.id})
    return sorted(out,key=lambda x:x["date"])
