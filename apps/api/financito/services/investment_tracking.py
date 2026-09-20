from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.portfolio import apply_trade
from ..models import Portfolio, Position, Security
from ..models_extended import AssetSimulation, CorporateAction, LotDisposal, MarketPrice, TrackedAsset, Trade


def ensure_default_portfolio(session: Session) -> Portfolio:
    row = session.scalar(select(Portfolio).where(Portfolio.name == "Principal"))
    if row:
        return row
    row = Portfolio(name="Principal", base_currency="EUR")
    session.add(row)
    session.flush()
    return row


def _position_rows(session: Session, security_id: str) -> list[Position]:
    return session.scalars(select(Position).where(Position.security_id == security_id)).all()


def _latest_market_price(session: Session, security_id: str) -> MarketPrice | None:
    return session.scalar(
        select(MarketPrice)
        .where(MarketPrice.security_id == security_id)
        .order_by(MarketPrice.timestamp.desc(), MarketPrice.fetched_at.desc())
        .limit(1)
    )


def _realized_pnl(session: Session, security_id: str) -> Decimal:
    trade_ids = [
        row.id
        for row in session.scalars(
            select(Trade).where(Trade.security_id == security_id, Trade.side == "sell")
        ).all()
    ]
    if not trade_ids:
        return Decimal("0")
    rows = session.scalars(select(LotDisposal).where(LotDisposal.trade_id.in_(trade_ids))).all()
    return sum((row.realized_pnl for row in rows), Decimal("0"))


def _dividends(session: Session, security_id: str) -> Decimal:
    rows = session.scalars(
        select(CorporateAction).where(
            CorporateAction.security_id == security_id,
            CorporateAction.action_type == "dividend",
        )
    ).all()
    return sum((row.value for row in rows), Decimal("0"))


def security_summary(session: Session, security: Security) -> dict:
    positions = _position_rows(session, security.id)
    quantity = sum((row.quantity for row in positions), Decimal("0"))
    total_basis = sum((row.quantity * row.average_cost for row in positions), Decimal("0"))
    average_cost = Decimal("0") if quantity <= 0 else total_basis / quantity

    latest = _latest_market_price(session, security.id)
    # A trade price is historical purchase/sale data, not a current quote.
    # Only a persisted market-provider observation may be labelled "current".
    current_price = latest.close if latest else None

    current_value = None if current_price is None else quantity * current_price
    unrealized = None if current_value is None else current_value - total_basis
    unrealized_pct = None
    if unrealized is not None and total_basis > 0:
        unrealized_pct = unrealized / total_basis

    realized = _realized_pnl(session, security.id)
    dividends = _dividends(session, security.id)
    total_result = None if unrealized is None else unrealized + realized + dividends

    tracking = session.scalar(select(TrackedAsset).where(TrackedAsset.security_id == security.id))
    simulation = session.scalar(select(AssetSimulation).where(AssetSimulation.security_id == security.id,AssetSimulation.active.is_(True)))
    provider_asset_id = tracking.provider_asset_id if tracking else None
    price_age_minutes = None
    price_stale = True
    if latest is not None:
        stamp = latest.fetched_at or latest.timestamp
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        price_age_minutes = max(0, int((datetime.now(timezone.utc) - stamp).total_seconds() // 60))
        price_stale = price_age_minutes > 15
    owned = quantity > 0
    state = "owned" if owned else (tracking.tracking_state if tracking else "untracked")

    portfolio_ids = sorted({row.portfolio_id for row in positions if row.quantity > 0})

    return {
        "security_id": security.id,
        "name": security.name,
        "identifier": security.symbol,
        "asset_class": security.asset_class,
        "currency": security.currency,
        "tracking_state": state,
        "provider_asset_id": provider_asset_id,
        "owned": owned,
        "portfolio_ids": portfolio_ids,
        "quantity": str(quantity),
        "average_cost": str(average_cost),
        "cost_basis": str(total_basis),
        "current_price": None if current_price is None else str(current_price),
        "current_value": None if current_value is None else str(current_value),
        "unrealized_pnl": None if unrealized is None else str(unrealized),
        "unrealized_return": None if unrealized_pct is None else str(unrealized_pct),
        "realized_pnl": str(realized),
        "dividends": str(dividends),
        "total_result": None if total_result is None else str(total_result),
        "price_provider": None if latest is None else latest.provider,
        "price_as_of": None if latest is None else latest.timestamp.isoformat(),
        "price_fetched_at": None if latest is None else latest.fetched_at.isoformat(),
        "price_delayed": None if latest is None else latest.is_delayed,
        "price_age_minutes": price_age_minutes,
        "price_stale": price_stale,
        "simulation": None if simulation is None else {
            "started_at": simulation.started_at.isoformat(),
            "invested_amount": str(simulation.invested_amount),
            "entry_price": str(simulation.entry_price),
            "quantity": str(simulation.quantity),
            "current_value": None if current_price is None else str(simulation.quantity*current_price),
            "pnl": None if current_price is None else str(simulation.quantity*current_price-simulation.invested_amount),
            "return": None if current_price is None or simulation.invested_amount<=0 else str((simulation.quantity*current_price-simulation.invested_amount)/simulation.invested_amount),
        },
    }


def tracked_assets(session: Session) -> list[dict]:
    tracked_ids = {
        row.security_id
        for row in session.scalars(select(TrackedAsset)).all()
    }
    held_ids = {
        row.security_id
        for row in session.scalars(select(Position).where(Position.quantity > 0)).all()
    }
    ids = tracked_ids | held_ids
    if not ids:
        return []
    securities = session.scalars(select(Security).where(Security.id.in_(ids))).all()
    rows = [security_summary(session, security) for security in securities]
    return sorted(rows, key=lambda row: (not row["owned"], row["asset_class"], row["name"].lower()))


def _find_security(session: Session, asset_class: str, identifier: str) -> Security | None:
    normalized = identifier.strip().upper() if asset_class != "crypto" else identifier.strip().lower()
    rows = session.scalars(select(Security).where(Security.asset_class == asset_class)).all()
    for row in rows:
        symbol = (row.symbol or "").strip()
        candidate = symbol.upper() if asset_class != "crypto" else symbol.lower()
        if candidate == normalized:
            return row
    return None


def save_tracked_asset(
    session: Session,
    *,
    asset_class: str,
    name: str,
    identifier: str,
    owned: bool,
    portfolio_id: str | None,
    quantity: Decimal | None,
    purchase_price: Decimal | None,
    purchase_date,
    fees: Decimal,
    fx_rate: Decimal,
    currency: str,
    provider_asset_id: str | None,
    notes: str | None,
) -> dict:
    identifier = identifier.strip()
    if not identifier:
        raise ValueError("Identifier is required")

    security = _find_security(session, asset_class, identifier)
    if security is None:
        security = Security(
            asset_class=asset_class,
            symbol=identifier,
            isin=None,
            name=name.strip() or identifier,
            currency=currency.upper(),
        )
        session.add(security)
        session.flush()
    else:
        if name.strip():
            security.name = name.strip()
        security.currency = currency.upper()

    tracking = session.scalar(select(TrackedAsset).where(TrackedAsset.security_id == security.id))
    if tracking is None:
        tracking = TrackedAsset(
            security_id=security.id,
            tracking_state="owned" if owned else "watching",
            provider_asset_id=(provider_asset_id or identifier) if asset_class == "crypto" else provider_asset_id,
            preferred_currency=currency.upper(),
            notes=notes,
        )
        session.add(tracking)
    else:
        tracking.tracking_state = "owned" if owned else "watching"
        if asset_class == "crypto":
            tracking.provider_asset_id = provider_asset_id or tracking.provider_asset_id or identifier
        elif provider_asset_id:
            tracking.provider_asset_id = provider_asset_id
        tracking.preferred_currency = currency.upper()
        tracking.notes = notes

    current_quantity = sum((row.quantity for row in _position_rows(session, security.id)), Decimal("0"))
    if not owned and current_quantity > 0:
        tracking.tracking_state = "owned"
        raise ValueError("Este activo tiene una posición real registrada. Registra una venta antes de marcarlo como no poseído.")

    if owned and current_quantity <= 0:
        if quantity is None or purchase_price is None or purchase_date is None:
            raise ValueError("Quantity, purchase price and purchase date are required for an owned asset")
        portfolio = session.get(Portfolio, portfolio_id) if portfolio_id else ensure_default_portfolio(session)
        if not portfolio:
            raise ValueError("Portfolio not found")
        executed_at = datetime.combine(purchase_date, time(hour=12), tzinfo=timezone.utc)
        trade = Trade(
            portfolio_id=portfolio.id,
            security_id=security.id,
            side="buy",
            quantity=quantity,
            price=purchase_price,
            fees=fees,
            currency=currency.upper(),
            fx_rate=fx_rate,
            executed_at=executed_at,
            source_type="manual_tracking",
            source_ref=None,
        )
        session.add(trade)
        session.flush()
        apply_trade(session, trade)

    session.flush()
    return security_summary(session, security)


def start_simulation(session:Session,security_id:str,amount:Decimal)->dict:
    if amount<=0:raise ValueError("Simulation amount must be positive")
    security=session.get(Security,security_id)
    if not security:raise ValueError("Security not found")
    latest=_latest_market_price(session,security_id)
    if latest is None or latest.close<=0:raise ValueError("No hay un precio de mercado disponible para iniciar la simulación")
    row=session.scalar(select(AssetSimulation).where(AssetSimulation.security_id==security_id))
    quantity=amount/latest.close
    if row is None:
        row=AssetSimulation(security_id=security_id,started_at=datetime.now(timezone.utc),invested_amount=amount,entry_price=latest.close,quantity=quantity,currency=security.currency,active=True)
        session.add(row)
    else:
        row.started_at=datetime.now(timezone.utc);row.invested_amount=amount;row.entry_price=latest.close;row.quantity=quantity;row.currency=security.currency;row.active=True
    session.flush()
    return security_summary(session,security)

def simulation_history(session:Session,security_id:str)->dict:
    simulation=session.scalar(select(AssetSimulation).where(AssetSimulation.security_id==security_id,AssetSimulation.active.is_(True)))
    if simulation is None:return {"security_id":security_id,"simulation":None,"rows":[]}
    prices=session.scalars(select(MarketPrice).where(MarketPrice.security_id==security_id,MarketPrice.timestamp>=simulation.started_at).order_by(MarketPrice.timestamp)).all()
    # El primer punto siempre representa la compra simulada aunque el proveedor no tenga una observación exacta en ese instante.
    rows=[{"timestamp":simulation.started_at,"price":str(simulation.entry_price),"value":str(simulation.invested_amount),"pnl":"0","return":"0","provider":"simulation_entry"}]
    for price in prices:
        value=simulation.quantity*price.close;pnl=value-simulation.invested_amount
        rows.append({"timestamp":price.timestamp,"price":str(price.close),"value":str(value),"pnl":str(pnl),"return":str(pnl/simulation.invested_amount if simulation.invested_amount else Decimal("0")),"provider":price.provider})
    return {"security_id":security_id,"simulation":{"started_at":simulation.started_at,"invested_amount":str(simulation.invested_amount),"entry_price":str(simulation.entry_price),"quantity":str(simulation.quantity),"currency":simulation.currency},"rows":rows}

def remove_tracking(session:Session,security_id:str)->dict:
    tracking=session.scalar(select(TrackedAsset).where(TrackedAsset.security_id==security_id))
    simulation=session.scalar(select(AssetSimulation).where(AssetSimulation.security_id==security_id))
    positions=_position_rows(session,security_id)
    owned=any(p.quantity>0 for p in positions)
    if simulation:session.delete(simulation)
    if tracking:session.delete(tracking)
    session.flush()
    return {"security_id":security_id,"tracking_removed":tracking is not None,"simulation_removed":simulation is not None,"owned_position_kept":owned}
