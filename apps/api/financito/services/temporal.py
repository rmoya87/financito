from __future__ import annotations

from collections import defaultdict
from datetime import date,datetime,time,timezone
from decimal import Decimal,ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,Mortgage,Security,Transaction
from ..models_extended import Asset,Liability,MarketPrice,Trade

Q=Decimal("0.01")
def _m(value:Decimal)->str:return str(value.quantize(Q,rounding=ROUND_HALF_UP))

def wealth_as_of(session:Session,as_of:date)->dict:
    today=date.today()
    if as_of>today:raise ValueError("as_of cannot be in the future")
    warnings=[]

    account_total=Decimal("0")
    account_rows=[]
    for account in session.scalars(select(Account)).all():
        created=account.created_at.date() if account.created_at else None
        if created and created>as_of:
            continue
        after=session.scalars(select(Transaction).where(Transaction.account_id==account.id,Transaction.booking_date>as_of)).all()
        derived=account.current_balance-sum((t.amount for t in after),Decimal("0"))
        account_total+=derived
        account_rows.append({"id":account.id,"name":account.name,"balance":_m(derived),"method":"current_balance_minus_later_transactions" if as_of<today else "current_balance","later_transactions":len(after)})
    if as_of<today:
        warnings.append("Los saldos bancarios históricos se reconstruyen desde el saldo actual menos movimientos posteriores; su exactitud depende de que el histórico importado sea completo.")

    asset_total=Decimal("0");unknown_assets=[]
    for asset in session.scalars(select(Asset)).all():
        if asset.valuation_date<=as_of:
            asset_total+=asset.current_value*asset.ownership_percentage/Decimal("100")
        else:
            unknown_assets.append({"id":asset.id,"name":asset.name,"valuation_date":str(asset.valuation_date)})
    if unknown_assets:
        warnings.append("Hay activos cuya única valoración disponible es posterior a la fecha solicitada y se excluyen del total conocido.")

    cutoff=datetime.combine(as_of,time.max,tzinfo=timezone.utc)
    quantities=defaultdict(lambda:Decimal("0"))
    securities={}
    trades=session.scalars(select(Trade).where(Trade.executed_at<=cutoff).order_by(Trade.executed_at)).all()
    for trade in trades:
        quantities[trade.security_id]+=trade.quantity if trade.side=="buy" else -trade.quantity
    if quantities:
        securities={s.id:s for s in session.scalars(select(Security).where(Security.id.in_(list(quantities)))).all()}
    investment_total=Decimal("0");unpriced=[]
    for security_id,quantity in quantities.items():
        if quantity<=0:continue
        price=session.scalar(select(MarketPrice).where(MarketPrice.security_id==security_id,MarketPrice.timestamp<=cutoff).order_by(MarketPrice.timestamp.desc()).limit(1))
        security=securities.get(security_id)
        if price is None:
            unpriced.append({"security_id":security_id,"name":security.name if security else security_id,"quantity":str(quantity)})
            continue
        investment_total+=quantity*price.close
    if unpriced:
        warnings.append("Hay posiciones históricas sin precio de mercado observado en o antes de la fecha y se excluyen del valor conocido.")

    current_only_debt=Decimal("0")
    if as_of==today:
        liabilities=sum((x.outstanding_amount*x.ownership_percentage/Decimal("100") for x in session.scalars(select(Liability)).all()),Decimal("0"))
        mortgages=sum((x.remaining_principal for x in session.scalars(select(Mortgage)).all()),Decimal("0"))
        current_only_debt=liabilities+mortgages
    else:
        warnings.append("Pasivos e hipotecas no tienen todavía un ledger histórico de principal; no se usan valores actuales para fingir deuda pasada.")

    known_gross=account_total+asset_total+investment_total
    known_net=known_gross-current_only_debt
    missing_components=len(unknown_assets)+len(unpriced)+(1 if as_of<today else 0)
    completeness="complete" if missing_components==0 else "partial"
    return {
        "as_of":str(as_of),
        "status":completeness,
        "known":{
            "accounts":_m(account_total),
            "manual_assets":_m(asset_total),
            "investments":_m(investment_total),
            "debt":_m(current_only_debt),
            "gross_assets":_m(known_gross),
            "net_worth":_m(known_net),
        },
        "accounts":account_rows,
        "unknown":{"assets":unknown_assets,"unpriced_positions":unpriced,"historical_debt":as_of<today},
        "methodology":{
            "accounts":"current balance minus transactions after as_of",
            "assets":"manual valuation only when valuation_date <= as_of",
            "investments":"trade quantities as-of * latest persisted market price <= as_of",
            "debt":"current values only when as_of is today",
        },
        "warnings":warnings,
    }
