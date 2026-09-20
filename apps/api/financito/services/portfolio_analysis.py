from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Portfolio,Position,Security
from ..models_extended import MarketPrice,Trade
from .market_data import portfolio_exposure
from ..domain.portfolio import portfolio_summary


def portfolio_fit(session:Session,portfolio_id:str,security_id:str,proposed_weight:Decimal=Decimal("0.10"))->dict:
    if proposed_weight<=0 or proposed_weight>=1:
        raise ValueError("proposed_weight must be between 0 and 1")
    portfolio=session.get(Portfolio,portfolio_id)
    security=session.get(Security,security_id)
    if not portfolio or not security:
        raise ValueError("Portfolio or security not found")
    exposure=portfolio_exposure(session,portfolio_id)
    class_weight=Decimal("0")
    security_weight=Decimal("0")
    for row in exposure["by_asset_class"]:
        if row["asset_class"]==security.asset_class:
            class_weight=Decimal(row["weight"])
    for row in exposure["positions"]:
        if row["security_id"]==security_id:
            security_weight=Decimal(row["weight"])
    post_class=class_weight*(Decimal("1")-proposed_weight)+proposed_weight
    post_security=security_weight*(Decimal("1")-proposed_weight)+proposed_weight
    class_component=max(Decimal("0"),Decimal("1")-max(Decimal("0"),post_class-Decimal("0.35"))/Decimal("0.65"))
    security_component=max(Decimal("0"),Decimal("1")-max(Decimal("0"),post_security-Decimal("0.20"))/Decimal("0.80"))
    diversity_component=max(Decimal("0"),Decimal("1")-class_weight)
    score=class_component*Decimal("0.45")+security_component*Decimal("0.35")+diversity_component*Decimal("0.20")
    warnings=[]
    if post_security>Decimal("0.25"):warnings.append("La posición propuesta superaría el 25% del valor de la cartera.")
    if post_class>Decimal("0.50"):warnings.append("La clase de activo propuesta superaría el 50% de la cartera.")
    if security_weight>0:warnings.append("El activo ya existe en la cartera; el cálculo refleja aumento de concentración.")
    return {
        "portfolio_id":portfolio_id,
        "security_id":security_id,
        "asset_class":security.asset_class,
        "proposed_weight":str(proposed_weight),
        "current_asset_class_weight":str(class_weight),
        "post_asset_class_weight":str(post_class),
        "current_security_weight":str(security_weight),
        "post_security_weight":str(post_security),
        "fit_score":float(score),
        "components":{
            "asset_class_concentration":float(class_component),
            "single_security_concentration":float(security_component),
            "diversification":float(diversity_component),
        },
        "warnings":warnings,
        "notice":"Indicador estructural de concentración/diversificación; no es una recomendación de inversión ni estima rentabilidad.",
    }


def _xirr(cashflows:list[tuple[date,float]])->float|None:
    if len(cashflows)<2 or not any(v<0 for _,v in cashflows) or not any(v>0 for _,v in cashflows):
        return None
    base=min(d for d,_ in cashflows)
    def npv(rate:float)->float:
        return sum(v/((1+rate)**(((d-base).days/365.0))) for d,v in cashflows)
    lo=-0.9999;hi=10.0
    flo=npv(lo);fhi=npv(hi)
    for _ in range(12):
        if flo==0:return lo
        if fhi==0:return hi
        if flo*fhi<=0:break
        hi*=2;fhi=npv(hi)
    if flo*fhi>0:return None
    for _ in range(120):
        mid=(lo+hi)/2;fm=npv(mid)
        if abs(fm)<1e-8:return mid
        if flo*fm<=0:hi=mid;fhi=fm
        else:lo=mid;flo=fm
    return (lo+hi)/2


def portfolio_performance(session:Session,portfolio_id:str)->dict:
    if not session.get(Portfolio,portfolio_id):
        raise ValueError("Portfolio not found")
    trades=session.scalars(select(Trade).where(Trade.portfolio_id==portfolio_id).order_by(Trade.executed_at,Trade.id)).all()
    current=portfolio_summary(session,portfolio_id)
    current_value=float(current["market_value"])
    if not trades:
        return {"portfolio_id":portfolio_id,"mwr":None,"twr":None,"observations":0,"coverage":0.0,"current_value":current["market_value"],"assumptions":["Sin operaciones registradas."]}

    cashflows=[]
    for trade in trades:
        gross=float(trade.quantity*trade.price)
        fees=float(trade.fees)
        fx=float(trade.fx_rate)
        value=(gross+fees)*fx if trade.side=="buy" else -(gross-fees)*fx
        cashflows.append((trade.executed_at.date(),-value))
    cashflows.append((date.today(),current_value))
    mwr=_xirr(cashflows)

    security_ids=sorted({t.security_id for t in trades})
    prices=session.scalars(select(MarketPrice).where(MarketPrice.security_id.in_(security_ids)).order_by(MarketPrice.timestamp)).all()
    price_events=defaultdict(list)
    for p in prices:price_events[p.timestamp.date()].append(p)
    trade_events=defaultdict(list)
    for t in trades:trade_events[t.executed_at.date()].append(t)
    dates=sorted(set(price_events)|set(trade_events))[-1500:]

    quantities=defaultdict(lambda:Decimal("0"))
    latest_price={}
    prev_value=0.0
    product=1.0
    evaluated=0
    skipped=0
    for day in dates:
        for p in price_events.get(day,[]):latest_price[p.security_id]=float(p.close)
        external_flow=0.0
        for t in trade_events.get(day,[]):
            amount=float(t.quantity*t.price+t.fees) if t.side=="buy" else -float(t.quantity*t.price-t.fees)
            external_flow+=amount*float(t.fx_rate)
            quantities[t.security_id]+=t.quantity if t.side=="buy" else -t.quantity
        held=[sid for sid,q in quantities.items() if q>0]
        if any(sid not in latest_price for sid in held):
            skipped+=1
            continue
        value=sum(float(quantities[sid])*latest_price[sid] for sid in held)
        if prev_value>0:
            period_return=(value-prev_value-external_flow)/prev_value
            if math.isfinite(period_return) and period_return>-1:
                product*=1+period_return;evaluated+=1
            else:skipped+=1
        prev_value=value
    twr=(product-1) if evaluated else None
    denom=max(1,evaluated+skipped)
    return {
        "portfolio_id":portfolio_id,
        "mwr":mwr,
        "twr":twr,
        "observations":evaluated,
        "coverage":evaluated/denom,
        "current_value":current["market_value"],
        "first_trade":str(trades[0].executed_at.date()),
        "last_trade":str(trades[-1].executed_at.date()),
        "assumptions":[
            "MWR usa flujos de compras/ventas, FX registrado y valoración actual de posiciones.",
            "TWR encadena retornos solo cuando todas las posiciones mantenidas tienen un precio persistido en esa fecha.",
            "No se ajusta automáticamente por dividendos o corporate actions no registrados.",
        ],
    }
