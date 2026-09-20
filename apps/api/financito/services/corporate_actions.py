from __future__ import annotations

from datetime import datetime,time,timezone
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..models import Position
from ..models_extended import CorporateAction,LotDisposal,TaxLot,Trade
from ..domain.portfolio import apply_trade


def _source_ref(portfolio_id:str,security_id:str,action_type:str,effective_date,value:Decimal,source_ref:str|None)->str:
    if source_ref:
        return source_ref
    raw="|".join([portfolio_id,security_id,action_type,str(effective_date),str(value)])
    return "manual:"+sha256(raw.encode()).hexdigest()


def rebuild_portfolio(session:Session,portfolio_id:str)->dict:
    trades=session.scalars(select(Trade).where(Trade.portfolio_id==portfolio_id)).all()
    trade_ids=[t.id for t in trades]
    if trade_ids:
        session.execute(delete(LotDisposal).where(LotDisposal.trade_id.in_(trade_ids)))
    session.execute(delete(TaxLot).where(TaxLot.portfolio_id==portfolio_id))
    session.execute(delete(Position).where(Position.portfolio_id==portfolio_id))
    actions=session.scalars(select(CorporateAction).where(CorporateAction.portfolio_id==portfolio_id)).all()
    for action in actions:
        action.applied=False

    events=[]
    for trade in trades:
        events.append((trade.executed_at,1,"trade",trade))
    for action in actions:
        stamp=datetime.combine(action.effective_date,time.min,tzinfo=timezone.utc)
        events.append((stamp,0,"action",action))
    events.sort(key=lambda row:(row[0],row[1],row[3].id))

    realized=Decimal("0")
    for _,_,kind,obj in events:
        if kind=="trade":
            result=apply_trade(session,obj)
            realized+=Decimal(result["realized_pnl"])
            continue
        action:CorporateAction=obj
        if action.action_type=="split":
            ratio=action.value
            position=session.scalar(select(Position).where(Position.portfolio_id==portfolio_id,Position.security_id==action.security_id))
            if position:
                position.quantity*=ratio
                if ratio:
                    position.average_cost/=ratio
            lots=session.scalars(select(TaxLot).where(
                TaxLot.portfolio_id==portfolio_id,
                TaxLot.security_id==action.security_id,
                TaxLot.quantity_remaining>0,
            )).all()
            for lot in lots:
                lot.quantity_original*=ratio
                lot.quantity_remaining*=ratio
                lot.unit_cost/=ratio
        action.applied=True
    session.flush()
    return {"trades":len(trades),"actions":len(actions),"realized_pnl":str(realized)}


def add_action(session:Session,portfolio_id:str,security_id:str,action_type:str,effective_date,value:Decimal,currency:str="EUR",notes:str|None=None,source_type:str="manual",source_ref:str|None=None)->CorporateAction:
    ref=_source_ref(portfolio_id,security_id,action_type,effective_date,value,source_ref)
    existing=session.scalar(select(CorporateAction).where(
        CorporateAction.portfolio_id==portfolio_id,
        CorporateAction.security_id==security_id,
        CorporateAction.action_type==action_type,
        CorporateAction.effective_date==effective_date,
        CorporateAction.source_ref==ref,
    ))
    if existing:
        return existing
    row=CorporateAction(
        portfolio_id=portfolio_id,
        security_id=security_id,
        action_type=action_type,
        effective_date=effective_date,
        value=value,
        currency=currency,
        source_type=source_type,
        source_ref=ref,
        notes=notes,
    )
    session.add(row);session.flush()
    rebuild_portfolio(session,portfolio_id)
    return row


def list_actions(session:Session,portfolio_id:str)->list[dict]:
    rows=session.scalars(select(CorporateAction).where(CorporateAction.portfolio_id==portfolio_id).order_by(CorporateAction.effective_date.desc(),CorporateAction.created_at.desc())).all()
    return [{
        "id":r.id,
        "security_id":r.security_id,
        "action_type":r.action_type,
        "effective_date":r.effective_date,
        "value":str(r.value),
        "currency":r.currency,
        "source_type":r.source_type,
        "notes":r.notes,
        "applied":r.applied,
    } for r in rows]
