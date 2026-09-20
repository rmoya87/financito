from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.portfolio import apply_trade
from ..models import Portfolio, Position, Security
from ..models_extended import CorporateAction, LotDisposal, MarketPrice, TrackedAsset, Trade


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
    current_price = latest.close if latest else None
    if current_price is None:
        priced_positions = [row.current_price for row in positions if row.current_price is not None]
        if priced_positions:
            current_price = priced_positions[-1]

    current_value = None if current_price is None else quantity * current_price
    unrealized = None if current_value is None else current_value - total_basis
    unrealized_pct = None
    if unrealized is not None and total_basis > 0:
        unrealized_pct = unrealized / total_basis

    realized = _realized_pnl(session, security.id)
    dividends = _dividends(session, security.id)
    total_result = None if unrealized is None else unrealized + realized + dividends

    tracking = session.scalar(select(TrackedAsset).where(TrackedAsset.security_id == security.id))
    provider_asset_id = tracking.provider_asset_id if tracking else None
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
