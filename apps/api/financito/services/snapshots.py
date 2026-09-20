from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,Mortgage
from ..models_extended import Asset,Liability
from ..models_analytics import EntitySnapshot


def record_snapshot(session:Session,entity_type:str,entity_id:str,values:dict,as_of:date|None=None,source:str="manual",confidence:Decimal=Decimal("1"))->EntitySnapshot:
    day=as_of or date.today()
    row=session.scalar(select(EntitySnapshot).where(
        EntitySnapshot.entity_type==entity_type,
        EntitySnapshot.entity_id==entity_id,
        EntitySnapshot.as_of_date==day,
    ))
    payload=json.dumps(values,ensure_ascii=False,sort_keys=True)
    if row:
        row.values_json=payload
        row.source=source
        row.confidence=confidence
    else:
        row=EntitySnapshot(entity_type=entity_type,entity_id=entity_id,as_of_date=day,values_json=payload,source=source,confidence=confidence)
        session.add(row)
    session.flush()
    return row


def latest_snapshot(session:Session,entity_type:str,entity_id:str,as_of:date)->EntitySnapshot|None:
    return session.scalar(select(EntitySnapshot).where(
        EntitySnapshot.entity_type==entity_type,
        EntitySnapshot.entity_id==entity_id,
        EntitySnapshot.as_of_date<=as_of,
    ).order_by(EntitySnapshot.as_of_date.desc()).limit(1))


def capture_current(session:Session,source:str="manual_capture")->dict:
    day=date.today()
    counts={"account":0,"asset":0,"liability":0,"mortgage":0}
    for row in session.scalars(select(Account)).all():
        record_snapshot(session,"account",row.id,{"balance":str(row.current_balance),"available_balance":None if row.available_balance is None else str(row.available_balance),"currency":row.currency},day,source)
        counts["account"]+=1
    for row in session.scalars(select(Asset)).all():
        record_snapshot(session,"asset",row.id,{"value":str(row.current_value),"ownership_percentage":str(row.ownership_percentage),"currency":row.currency},day,source)
        counts["asset"]+=1
    for row in session.scalars(select(Liability)).all():
        record_snapshot(session,"liability",row.id,{"outstanding_amount":str(row.outstanding_amount),"ownership_percentage":str(row.ownership_percentage),"currency":row.currency},day,source)
        counts["liability"]+=1
    for row in session.scalars(select(Mortgage)).all():
        record_snapshot(session,"mortgage",row.id,{"remaining_principal":str(row.remaining_principal),"currency":row.currency},day,source)
        counts["mortgage"]+=1
    return {"as_of":str(day),"captured":counts}
