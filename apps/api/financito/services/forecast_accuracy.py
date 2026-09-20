from __future__ import annotations
from calendar import monthrange
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy.orm import Session
from .forecast import forecast,_sum_transactions
Q=Decimal("0.01")
def evaluate(session:Session,months:int=6,as_of:date|None=None)->dict:
    as_of=as_of or date.today();cursor=as_of.replace(day=1);samples=[]
    for _ in range(months):
        prev_end=cursor.fromordinal(cursor.toordinal()-1);start=prev_end.replace(day=1);end=prev_end
        result=forecast(session,start,end);actual=_sum_transactions(session,start,end,False)
        error=result.predicted_expenses-actual;absolute=abs(error);covered=result.lower_bound<=actual<=result.upper_bound
        samples.append({"start":str(start),"end":str(end),"predicted":str(result.predicted_expenses),"actual":str(actual),"error":str(error),"absolute_error":str(absolute),"interval_covered":covered})
        cursor=start
    valid=[s for s in samples if Decimal(s["actual"])>0]
    if not valid:return {"sample_count":0,"mae":None,"wape":None,"bias":None,"interval_coverage":None,"samples":samples}
    mae=sum((Decimal(s["absolute_error"]) for s in valid),Decimal("0"))/len(valid)
    total_actual=sum((Decimal(s["actual"]) for s in valid),Decimal("0"))
    wape=sum((Decimal(s["absolute_error"]) for s in valid),Decimal("0"))/total_actual if total_actual else None
    bias=sum((Decimal(s["error"]) for s in valid),Decimal("0"))/len(valid)
    coverage=Decimal(sum(1 for s in valid if s["interval_covered"]))/Decimal(len(valid))
    fmt=lambda x:None if x is None else str(x.quantize(Q,rounding=ROUND_HALF_UP))
    return {"sample_count":len(valid),"mae":fmt(mae),"wape":None if wape is None else str(wape.quantize(Decimal("0.0001"))),"bias":fmt(bias),"interval_coverage":str(coverage.quantize(Decimal("0.0001"))),"model_version":result.model_version,"samples":samples}
