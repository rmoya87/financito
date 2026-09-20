from datetime import datetime,timezone,date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from financito.db import SessionLocal
from financito.domain.portfolio import apply_trade
from financito.models import Portfolio,Position,Security
from financito.models_extended import CorporateAction,TaxLot,Trade
from financito.services.corporate_actions import add_action
from financito.services.portfolio_analysis import portfolio_performance


def _trade(portfolio_id,security_id,side,qty,price,when):
    return Trade(
        portfolio_id=portfolio_id,security_id=security_id,side=side,
        quantity=Decimal(qty),price=Decimal(price),fees=Decimal("0"),
        currency="EUR",fx_rate=Decimal("1"),executed_at=when,
        source_type="test",
    )


def test_historical_split_rebuilds_only_pre_split_holdings():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        p=Portfolio(name=f"Corp {suffix}",base_currency="EUR")
        s=Security(asset_class="stock",name=f"Corp asset {suffix}",symbol=f"C{suffix[:5]}",currency="EUR")
        db.add_all([p,s]);db.flush()
        t1=_trade(p.id,s.id,"buy","10","100",datetime(2026,1,1,tzinfo=timezone.utc))
        t2=_trade(p.id,s.id,"buy","5","60",datetime(2026,2,1,tzinfo=timezone.utc))
        db.add(t1);db.flush();apply_trade(db,t1)
        db.add(t2);db.flush();apply_trade(db,t2)
        action=add_action(db,p.id,s.id,"split",date(2026,1,15),Decimal("2"))
        position=db.scalar(select(Position).where(Position.portfolio_id==p.id,Position.security_id==s.id))
        assert position is not None
        assert position.quantity==Decimal("25")
        lots=db.scalars(select(TaxLot).where(TaxLot.portfolio_id==p.id).order_by(TaxLot.acquisition_date)).all()
        assert lots[0].quantity_original==Decimal("20")
        assert lots[0].unit_cost==Decimal("50")
        assert lots[1].quantity_original==Decimal("5")
        assert lots[1].unit_cost==Decimal("60")
        assert action.applied is True


def test_dividend_does_not_change_quantity_and_is_part_of_performance_cashflows():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        p=Portfolio(name=f"Dividend {suffix}",base_currency="EUR")
        s=Security(asset_class="stock",name=f"Dividend asset {suffix}",symbol=f"D{suffix[:5]}",currency="EUR")
        db.add_all([p,s]);db.flush()
        t=_trade(p.id,s.id,"buy","10","100",datetime(2026,1,1,tzinfo=timezone.utc))
        db.add(t);db.flush();apply_trade(db,t)
        before=db.scalar(select(Position).where(Position.portfolio_id==p.id,Position.security_id==s.id)).quantity
        action=add_action(db,p.id,s.id,"dividend",date(2026,2,1),Decimal("50"))
        after=db.scalar(select(Position).where(Position.portfolio_id==p.id,Position.security_id==s.id)).quantity
        assert before==after==Decimal("10")
        assert action.applied is True
        perf=portfolio_performance(db,p.id)
        assert perf["mwr"] is not None
