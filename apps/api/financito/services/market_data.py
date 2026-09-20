from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.risk import risk_metrics
from ..models import Portfolio,Position,Security
from ..models_extended import MarketPrice,TrackedAsset
from ..providers.market import AlphaVantageProvider,StooqProvider
from ..providers.crypto import CoinGeckoDemoProvider

def refresh_security(session:Session,security_id:str,provider:AlphaVantageProvider|None=None)->dict:
    security=session.get(Security,security_id)
    if not security:raise ValueError("Security not found")
    if not security.symbol:raise ValueError("Security has no market symbol")

    if security.asset_class=="crypto":
        tracking=session.scalar(select(TrackedAsset).where(TrackedAsset.security_id==security.id))
        coin_id=(tracking.provider_asset_id if tracking and tracking.provider_asset_id else security.symbol).strip().lower()
        data=CoinGeckoDemoProvider().simple_price([coin_id],security.currency.lower())
        row=data.get(coin_id)
        if not row or security.currency.lower() not in row:
            raise ValueError("Crypto price unavailable")
        price=Decimal(str(row[security.currency.lower()]))
        updated=row.get("last_updated_at")
        try:stamp=datetime.fromtimestamp(int(updated),timezone.utc) if updated else datetime.now(timezone.utc)
        except Exception:stamp=datetime.now(timezone.utc)
        for pos in session.scalars(select(Position).where(Position.security_id==security.id)).all():
            pos.current_price=price
        existing=session.scalar(select(MarketPrice).where(MarketPrice.security_id==security.id,MarketPrice.timestamp==stamp,MarketPrice.provider=="coingecko"))
        if existing:existing.close=price;existing.fetched_at=datetime.now(timezone.utc)
        else:session.add(MarketPrice(security_id=security.id,timestamp=stamp,close=price,currency=security.currency,provider="coingecko",is_delayed=False))
        session.flush()
        return {"security_id":security.id,"symbol":security.symbol,"price":str(price),"provider":"CoinGecko","as_of":stamp.isoformat(),"delayed":False}

    providers=[provider] if provider is not None else []
    if provider is None:
        try:providers.append(AlphaVantageProvider())
        except Exception:pass
        providers.append(StooqProvider())
    quote=None;errors=[]
    for candidate in providers:
        try:
            quote=candidate.quote(security.symbol)
            break
        except Exception as exc:
            errors.append(str(exc))
    if quote is None:
        raise ValueError("No se pudo obtener una cotización gratuita. "+" · ".join(x for x in errors if x))
    price=Decimal(quote["price"])
    for pos in session.scalars(select(Position).where(Position.security_id==security.id)).all():
        pos.current_price=price
    as_of=quote.get("as_of")
    try:stamp=datetime.fromisoformat(str(as_of)).replace(tzinfo=timezone.utc)
    except Exception:stamp=datetime.now(timezone.utc)
    existing=session.scalar(select(MarketPrice).where(MarketPrice.security_id==security.id,MarketPrice.timestamp==stamp,MarketPrice.provider==quote.get("provider","market")))
    if existing:existing.close=price;existing.fetched_at=datetime.now(timezone.utc)
    else:session.add(MarketPrice(security_id=security.id,timestamp=stamp,close=price,currency=security.currency,provider=quote.get("provider","market"),is_delayed=bool(quote.get("delayed",True))))
    session.flush()
    return {"security_id":security.id,**quote}

def refresh_history(session:Session,security_id:str,provider:AlphaVantageProvider|None=None)->dict:
    security=session.get(Security,security_id)
    if not security:raise ValueError("Security not found")
    if not security.symbol:raise ValueError("Security has no market symbol")

    if security.asset_class=="crypto":
        tracking=session.scalar(select(TrackedAsset).where(TrackedAsset.security_id==security.id))
        coin_id=(tracking.provider_asset_id if tracking and tracking.provider_asset_id else security.symbol).strip().lower()
        chart=CoinGeckoDemoProvider().market_chart(coin_id,security.currency.lower(),365)
        rows=chart.get("prices",[]);inserted=updated=0
        latest_price=None
        latest_stamp=None
        for raw in rows:
            if len(raw)<2:continue
            stamp=datetime.fromtimestamp(float(raw[0])/1000,timezone.utc)
            price=Decimal(str(raw[1]))
            existing=session.scalar(select(MarketPrice).where(MarketPrice.security_id==security.id,MarketPrice.timestamp==stamp,MarketPrice.provider=="coingecko"))
            if existing:existing.close=price;existing.fetched_at=datetime.now(timezone.utc);updated+=1
            else:session.add(MarketPrice(security_id=security.id,timestamp=stamp,close=price,currency=security.currency,provider="coingecko",is_delayed=False));inserted+=1
            if latest_stamp is None or stamp>latest_stamp:latest_stamp=stamp;latest_price=price
        if latest_price is not None:
            for pos in session.scalars(select(Position).where(Position.security_id==security.id)).all():pos.current_price=latest_price
        session.flush();return {"security_id":security.id,"inserted":inserted,"updated":updated,"provider":"coingecko"}

    providers=[provider] if provider is not None else []
    if provider is None:
        try:providers.append(AlphaVantageProvider())
        except Exception:pass
        providers.append(StooqProvider())
    rows=None;provider_name=None;errors=[]
    for candidate in providers:
        try:
            rows=candidate.daily(security.symbol)
            provider_name="alpha_vantage" if isinstance(candidate,AlphaVantageProvider) else "stooq"
            break
        except Exception as exc:
            errors.append(str(exc))
    if rows is None:
        raise ValueError("No se pudo obtener histórico gratuito. "+" · ".join(x for x in errors if x))
    inserted=updated=0
    for row in rows:
        stamp=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc);price=Decimal(str(row["close"]))
        existing=session.scalar(select(MarketPrice).where(MarketPrice.security_id==security.id,MarketPrice.timestamp==stamp,MarketPrice.provider==provider_name))
        if existing:existing.close=price;existing.fetched_at=datetime.now(timezone.utc);updated+=1
        else:session.add(MarketPrice(security_id=security.id,timestamp=stamp,close=price,currency=security.currency,provider=provider_name,is_delayed=True));inserted+=1
    if rows:
        latest=max(rows,key=lambda x:x["date"])
        for pos in session.scalars(select(Position).where(Position.security_id==security.id)).all():pos.current_price=Decimal(str(latest["close"]))
    session.flush();return {"security_id":security.id,"inserted":inserted,"updated":updated,"provider":provider_name}

def history(session:Session,security_id:str)->list[dict]:
    rows=session.scalars(select(MarketPrice).where(MarketPrice.security_id==security_id).order_by(MarketPrice.timestamp)).all()
    return [{"timestamp":r.timestamp,"close":str(r.close),"currency":r.currency,"provider":r.provider,"fetched_at":r.fetched_at,"delayed":r.is_delayed} for r in rows]

def portfolio_exposure(session:Session,portfolio_id:str)->dict:
    portfolio=session.get(Portfolio,portfolio_id)
    if not portfolio:raise ValueError("Portfolio not found")
    positions=session.scalars(select(Position).where(Position.portfolio_id==portfolio_id)).all()
    securities={s.id:s for s in session.scalars(select(Security).where(Security.id.in_([p.security_id for p in positions]))).all()} if positions else {}
    values=[]
    for p in positions:
        price=p.current_price or p.average_cost;value=p.quantity*price
        values.append((p,securities.get(p.security_id),value))
    total=sum((x[2] for x in values),Decimal("0"))
    by_class=defaultdict(lambda:Decimal("0"));weights=[]
    for p,s,value in values:
        key=s.asset_class if s else "unknown";by_class[key]+=value
        w=Decimal("0") if total==0 else value/total
        weights.append({"security_id":p.security_id,"name":s.name if s else p.security_id,"symbol":s.symbol if s else None,"value":str(value),"weight":str(w)})
    hhi=sum((Decimal(x["weight"])**2 for x in weights),Decimal("0"))
    return {"portfolio_id":portfolio_id,"market_value":str(total),"by_asset_class":[{"asset_class":k,"value":str(v),"weight":str(Decimal("0") if total==0 else v/total)} for k,v in sorted(by_class.items())],"positions":sorted(weights,key=lambda x:Decimal(x["weight"]),reverse=True),"concentration_hhi":str(hhi),"largest_position_weight":weights and max((Decimal(x["weight"]) for x in weights),default=Decimal("0")) or Decimal("0")}

def security_risk(session:Session,security_id:str)->dict:
    rows=session.scalars(select(MarketPrice).where(MarketPrice.security_id==security_id).order_by(MarketPrice.timestamp)).all()
    prices=[float(r.close) for r in rows]
    return {"security_id":security_id,"metrics":risk_metrics(prices),"first":rows[0].timestamp if rows else None,"last":rows[-1].timestamp if rows else None,"provider_set":sorted({r.provider for r in rows})}
