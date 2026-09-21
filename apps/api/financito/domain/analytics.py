from __future__ import annotations

import json
import re
from datetime import timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import ActionItem, Transaction
from ..models_analytics import Anomaly, RecurringSeries
from ..services import local_ai


CADENCE_RANGES={
    "weekly":(5,9),
    "monthly":(24,38),
    "quarterly":(75,105),
    "annual":(330,400),
}


def _infer_cadence(items:list[Transaction])->tuple[str|None,float]:
    ordered=sorted(items,key=lambda x:x.booking_date)
    dates=[]
    for item in ordered:
        if not dates or item.booking_date!=dates[-1]:
            dates.append(item.booking_date)
    if len(dates)<3:
        return None,0.0
    gaps=[(dates[i]-dates[i-1]).days for i in range(1,len(dates))]
    med=float(median(gaps))
    cadence=next((name for name,(lo,hi) in CADENCE_RANGES.items() if lo<=med<=hi),None)
    if cadence is None:
        return None,med
    deviations=[abs(g-med) for g in gaps]
    typical=float(median(deviations)) if deviations else 0.0
    limit={"weekly":2.5,"monthly":6.0,"quarterly":12.0,"annual":25.0}[cadence]
    if typical>limit:
        return None,med
    return cadence,med


def _description_family(tx:Transaction)->str:
    value=(tx.description_normalized or tx.description_raw or "").lower()
    value=re.sub(r"\b\d{2,}\b"," ",value)
    value=re.sub(r"\b(?:ref|recibo|factura|pedido|operacion|operación|id)\s*[:#-]?\s*\w+"," ",value)
    value=re.sub(r"[^a-záéíóúüñ ]+"," ",value)
    value=re.sub(r"\s+"," ",value).strip()
    return value[:120]


def _add_price_increase_action(session:Session,label:str,amounts:list[Decimal])->None:
    if len(amounts)<4:
        return
    previous=Decimal(str(median(amounts[:-1])))
    if previous<=0 or amounts[-1]<=previous*Decimal("1.10"):
        return
    exists=session.scalar(select(ActionItem.id).where(
        ActionItem.action_type=="recurring_price_increase",
        ActionItem.source_ref==label,
        ActionItem.status=="pending",
    ))
    if not exists:
        session.add(ActionItem(
            action_type="recurring_price_increase",
            title="Revisar subida de "+label,
            priority="medium",
            source_type="recurring",
            source_ref=label,
            expected_impact_json=json.dumps({"latest":str(amounts[-1]),"previous_typical":str(previous)}),
        ))


def _create_series(session:Session,label:str,items:list[Transaction],confidence:Decimal)->RecurringSeries|None:
    unique={item.id:item for item in items}
    ordered=sorted(unique.values(),key=lambda x:x.booking_date)
    cadence,gap=_infer_cadence(ordered)
    if cadence is None or len(ordered)<3:
        return None
    amounts=[-item.amount for item in ordered if item.amount<0]
    if len(amounts)<3:
        return None
    expected=Decimal(str(median(amounts)))
    deviations=[abs(value-expected) for value in amounts]
    amount_mad=Decimal(str(median(deviations))) if deviations else Decimal("0")
    tolerance=max(Decimal("1"),expected*Decimal("0.15"),amount_mad*Decimal("2.5"))
    row=RecurringSeries(
        merchant_normalized=label[:240],
        cadence=cadence,
        expected_amount=expected,
        amount_tolerance=tolerance,
        next_expected_date=ordered[-1].booking_date+timedelta(days=round(gap)),
        confidence=confidence,
    )
    session.add(row)
    for item in ordered:
        item.is_recurring=True
    _add_price_increase_action(session,label,amounts)
    return row


def _ai_series(session:Session,candidates:list[Transaction])->list[tuple[str,list[Transaction],Decimal]]:
    if len(candidates)<3:
        return []
    info=local_ai.status()
    if not (info.get("available") and info.get("chat_ready")):
        return []
    selected=sorted(candidates,key=lambda x:x.booking_date,reverse=True)[:160]
    payload=[{
        "id":tx.id,
        "date":tx.booking_date.isoformat(),
        "amount":str(-tx.amount),
        "merchant":tx.merchant_raw,
        "description":tx.description_raw,
        "category_id":tx.category_id,
    } for tx in selected]
    prompt=(
        "Analiza gastos bancarios personales para detectar SOLO patrones repetidos reales. "
        "Agrupa movimientos que representen el mismo gasto aunque cambien referencias o el nombre del comercio. "
        "Son útiles ejemplos como colegio, supermercado/alimentación, suministros, seguros, gimnasio, "
        "suscripciones, transporte o cuotas. No agrupes por parecido semántico si las fechas no muestran repetición. "
        "Devuelve SOLO JSON {\"series\":[{\"label\":\"...\",\"transaction_ids\":[\"...\"],"
        "\"confidence\":0.0}]}. Cada serie debe tener al menos 3 movimientos. "
        "No calcules importes, fechas futuras ni periodicidad: Financito los validará matemáticamente. "
        "Si no hay patrones claros devuelve {\"series\":[]}. Movimientos: "+json.dumps(payload,ensure_ascii=False)
    )
    try:
        data=local_ai.generate_json(prompt,timeout=240)
    except Exception:
        return []
    by_id={tx.id:tx for tx in selected}
    used=set()
    out=[]
    for raw in data.get("series",[]) or []:
        if not isinstance(raw,dict):
            continue
        ids=[str(x) for x in raw.get("transaction_ids",[]) if str(x) in by_id and str(x) not in used]
        items=[by_id[x] for x in ids]
        cadence,_=_infer_cadence(items)
        if cadence is None or len(items)<3:
            continue
        try:
            score=float(raw.get("confidence",0))
        except Exception:
            score=0
        if score<0.65:
            continue
        label=str(raw.get("label") or items[0].merchant_normalized or _description_family(items[0]) or "Patrón recurrente").strip()
        confidence=Decimal(str(min(0.88,max(0.70,score)))).quantize(Decimal("0.0001"))
        out.append((label,items,confidence))
        used.update(ids)
    return out


def detect_recurring(session:Session,use_ai:bool=True)->list[RecurringSeries]:
    txs=session.scalars(
        select(Transaction)
        .where(Transaction.amount<0,Transaction.is_internal_transfer.is_(False))
        .order_by(Transaction.booking_date)
    ).all()
    session.execute(delete(RecurringSeries))
    session.execute(update(Transaction).values(is_recurring=False))
    out=[];used=set()

    merchant_groups={}
    for tx in txs:
        if tx.merchant_normalized:
            merchant_groups.setdefault(tx.merchant_normalized,[]).append(tx)
    for merchant,items in merchant_groups.items():
        row=_create_series(session,merchant,items,Decimal("0.90") if len(items)>=6 else Decimal("0.78"))
        if row:
            out.append(row);used.update(x.id for x in items)

    description_groups={}
    for tx in txs:
        if tx.id in used:
            continue
        family=_description_family(tx)
        if len(family)<5:
            continue
        key=(tx.category_id or "uncategorized",family)
        description_groups.setdefault(key,[]).append(tx)
    for (_,family),items in description_groups.items():
        row=_create_series(session,family,items,Decimal("0.74"))
        if row:
            out.append(row);used.update(x.id for x in items)

    if use_ai:
        unresolved=[tx for tx in txs if tx.id not in used]
        for label,items,confidence in _ai_series(session,unresolved):
            row=_create_series(session,label,items,confidence)
            if row:
                out.append(row);used.update(x.id for x in items)
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
