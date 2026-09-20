from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models_extended import LotDisposal,Trade
Q=Decimal("0.01")
def estimate(session:Session,jurisdiction:str,tax_year:int,assumed_rate:Decimal|None=None)->dict:
    start=datetime(tax_year,1,1,tzinfo=timezone.utc);end=datetime(tax_year+1,1,1,tzinfo=timezone.utc)
    rows=session.execute(select(LotDisposal.realized_pnl).join(Trade,Trade.id==LotDisposal.trade_id).where(Trade.executed_at>=start,Trade.executed_at<end)).scalars().all()
    realized=sum(rows,Decimal("0"));positive=max(Decimal("0"),realized)
    tax=None if assumed_rate is None else (positive*assumed_rate).quantize(Q,rounding=ROUND_HALF_UP)
    return {"jurisdiction":jurisdiction,"tax_year":tax_year,"realized_pnl":str(realized.quantize(Q)),"estimated_tax":None if tax is None else str(tax),"assumed_rate":None if assumed_rate is None else str(assumed_rate),"status":"needs_rate" if assumed_rate is None else "estimate","notice":"Estimación informativa; no constituye declaración fiscal oficial. La tasa se exige explícita hasta instalar un módulo normativo versionado para la jurisdicción y ejercicio."}
