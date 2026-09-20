from __future__ import annotations

from collections import defaultdict
from datetime import date,datetime,time,timezone
from decimal import Decimal,ROUND_HALF_UP
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,Mortgage,Security,Transaction
from ..models_extended import Asset,Liability,MarketPrice,Trade
from .snapshots import latest_snapshot

Q=Decimal("0.01")

def _m(value:Decimal)->str:
    return str(value.quantize(Q,rounding=ROUND_HALF_UP))


def wealth_as_of(session:Session,as_of:date)->dict:
    today=date.today()
    if as_of>today:
        raise ValueError("as_of cannot be in the future")
    warnings=[]

    account_total=Decimal("0")
    account_rows=[]
    used_account_fallback=False
    for account in session.scalars(select(Account)).all():
        created=account.created_at.date() if account.created_at else None
        if created and created>as_of:
            continue
        snap=latest_snapshot(session,"account",account.id,as_of)
        if snap:
            values=json.loads(snap.values_json)
            derived=Decimal(values["balance"])
            method="snapshot"
            later_count=0
            snapshot_date=str(snap.as_of_date)
        else:
            after=session.scalars(select(Transaction).where(Transaction.account_id==account.id,Transaction.booking_date>as_of)).all()
            derived=account.current_balance-sum((t.amount for t in after),Decimal("0"))
            method="current_balance_minus_later_transactions" if as_of<today else "current_balance"
            later_count=len(after)
            snapshot_date=None
            used_account_fallback=used_account_fallback or as_of<today
        account_total+=derived
        account_rows.append({
            "id":account.id,
            "name":account.name,
            "balance":_m(derived),
            "method":method,
            "later_transactions":later_count,
            "snapshot_date":snapshot_date,
        })
    if used_account_fallback:
        warnings.append("Algunos saldos históricos se reconstruyen desde el saldo actual menos movimientos posteriores; su exactitud depende de que el histórico importado sea completo.")

    asset_total=Decimal("0")
    unknown_assets=[]
    for asset in session.scalars(select(Asset)).all():
        snap=latest_snapshot(session,"asset",asset.id,as_of)
        if snap:
            values=json.loads(snap.values_json)
            asset_total+=Decimal(values["value"])*Decimal(values.get("ownership_percentage","100"))/Decimal("100")
        elif asset.valuation_date<=as_of:
            asset_total+=asset.current_value*asset.ownership_percentage/Decimal("100")
        else:
            unknown_assets.append({"id":asset.id,"name":asset.name,"valuation_date":str(asset.valuation_date)})
    if unknown_assets:
        warnings.append("Hay activos cuya primera valoración disponible es posterior a la fecha solicitada y se excluyen del total conocido.")

    cutoff=datetime.combine(as_of,time.max,tzinfo=timezone.utc)
    quantities=defaultdict(lambda:Decimal("0"))
    trades=session.scalars(select(Trade).where(Trade.executed_at<=cutoff).order_by(Trade.executed_at)).all()
    for trade in trades:
        quantities[trade.security_id]+=trade.quantity if trade.side=="buy" else -trade.quantity
    securities={}
    if quantities:
        securities={s.id:s for s in session.scalars(select(Security).where(Security.id.in_(list(quantities)))).all()}
    investment_total=Decimal("0")
    unpriced=[]
    for security_id,quantity in quantities.items():
        if quantity<=0:
            continue
        price=session.scalar(
            select(MarketPrice)
            .where(MarketPrice.security_id==security_id,MarketPrice.timestamp<=cutoff)
            .order_by(MarketPrice.timestamp.desc())
            .limit(1)
        )
        security=securities.get(security_id)
        if price is None:
            unpriced.append({"security_id":security_id,"name":security.name if security else security_id,"quantity":str(quantity)})
            continue
        investment_total+=quantity*price.close
    if unpriced:
        warnings.append("Hay posiciones históricas sin precio de mercado observado en o antes de la fecha y se excluyen del valor conocido.")

    debt_total=Decimal("0")
    unknown_debt=[]
    for row in session.scalars(select(Liability)).all():
        snap=latest_snapshot(session,"liability",row.id,as_of)
        if snap:
            values=json.loads(snap.values_json)
            debt_total+=Decimal(values["outstanding_amount"])*Decimal(values.get("ownership_percentage","100"))/Decimal("100")
        elif as_of==today:
            debt_total+=row.outstanding_amount*row.ownership_percentage/Decimal("100")
        else:
            unknown_debt.append({"type":"liability","id":row.id,"name":row.name})
    for row in session.scalars(select(Mortgage)).all():
        snap=latest_snapshot(session,"mortgage",row.id,as_of)
        if snap:
            values=json.loads(snap.values_json)
            debt_total+=Decimal(values["remaining_principal"])
        elif as_of==today:
            debt_total+=row.remaining_principal
        else:
            unknown_debt.append({"type":"mortgage","id":row.id,"name":row.lender})
    if unknown_debt:
        warnings.append("Parte de la deuda no tiene snapshot histórico en o antes de la fecha solicitada y se excluye del total conocido.")

    known_gross=account_total+asset_total+investment_total
    known_net=known_gross-debt_total
    missing_components=len(unknown_assets)+len(unpriced)+len(unknown_debt)+(1 if used_account_fallback else 0)
    completeness="complete" if missing_components==0 else "partial"
    return {
        "as_of":str(as_of),
        "status":completeness,
        "known":{
            "accounts":_m(account_total),
            "manual_assets":_m(asset_total),
            "investments":_m(investment_total),
            "debt":_m(debt_total),
            "gross_assets":_m(known_gross),
            "net_worth":_m(known_net),
        },
        "accounts":account_rows,
        "unknown":{
            "assets":unknown_assets,
            "unpriced_positions":unpriced,
            "historical_debt":bool(unknown_debt),
            "debt":unknown_debt,
        },
        "methodology":{
            "accounts":"nearest daily snapshot <= as_of; fallback current balance minus transactions after as_of",
            "assets":"nearest daily snapshot <= as_of; fallback manual valuation when valuation_date <= as_of",
            "investments":"trade quantities as-of * latest persisted market price <= as_of",
            "debt":"nearest daily snapshot <= as_of; current values only for today when no snapshot exists",
        },
        "warnings":warnings,
    }
