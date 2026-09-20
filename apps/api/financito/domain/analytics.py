from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from statistics import median
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from ..models import ActionItem,Transaction
from ..models_analytics import Anomaly,RecurringSeries

def detect_recurring(session:Session)->list[RecurringSeries]:
    txs=session.scalars(select(Transaction).where(Transaction.amount<0,Transaction.is_internal_transfer.is_(False),Transaction.merchant_normalized.is_not(None)).order_by(Transaction.merchant_normalized,Transaction.booking_date)).all()
    groups={}
    for t in txs:groups.setdefault(t.merchant_normalized,[]).append(t)
    session.execute(delete(RecurringSeries));out=[]
    for merchant,items in groups.items():
        if len(items)<3:continue
        gaps=[(items[i].booking_date-items[i-1].booking_date).days for i in range(1,len(items))];med=median(gaps)
        cadence="monthly" if 25<=med<=35 else "weekly" if 6<=med<=8 else "quarterly" if 80<=med<=100 else "annual" if 340<=med<=390 else None
        if not cadence:continue
        amounts=[-i.amount for i in items];expected=Decimal(str(median(amounts)));tol=max(Decimal("1"),expected*Decimal("0.15"));confidence=Decimal("0.90") if len(items)>=6 else Decimal("0.75")
        r=RecurringSeries(merchant_normalized=merchant,cadence=cadence,expected_amount=expected,amount_tolerance=tol,next_expected_date=items[-1].booking_date+timedelta(days=round(med)),confidence=confidence);session.add(r);out.append(r)
        for tx in items: tx.is_recurring=True
        if len(amounts)>=4 and amounts[-1]>Decimal(str(median(amounts[:-1])))*Decimal("1.10"):
            exists=session.scalar(select(ActionItem.id).where(ActionItem.action_type=="recurring_price_increase",ActionItem.source_ref==merchant,ActionItem.status=="pending"))
            if not exists:session.add(ActionItem(action_type="recurring_price_increase",title="Revisar subida de "+merchant,priority="medium",source_type="recurring",source_ref=merchant,expected_impact_json='{"latest":"'+str(amounts[-1])+'"}'))
    return out

def detect_anomalies(session:Session)->list[Anomaly]:
    session.execute(delete(Anomaly).where(Anomaly.status=="open"));out=[]
    txs=session.scalars(select(Transaction).where(Transaction.amount<0,Transaction.is_internal_transfer.is_(False))).all();groups={}
    for t in txs:groups.setdefault(t.category_id or "uncategorized",[]).append(t)
    for _,items in groups.items():
        vals=sorted([-t.amount for t in items])
        if len(vals)<5:continue
        med=Decimal(str(median(vals)));devs=[abs(v-med) for v in vals];mad=Decimal(str(median(devs))) or Decimal("1")
        for t in items:
            val=-t.amount;score=abs(val-med)/mad
            if score>=Decimal("6"):
                a=Anomaly(transaction_id=t.id,anomaly_type="amount_outlier",baseline_json='{"median":"'+str(med)+'","mad":"'+str(mad)+'"}',observed_json='{"amount":"'+str(val)+'"}',explanation="Importe muy alejado del patrón histórico de su categoría.",confidence=min(Decimal("0.99"),Decimal("0.6")+score/Decimal("20")));session.add(a);out.append(a)
    return out
