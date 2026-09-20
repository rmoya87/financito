from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Position
from ..models_extended import LotDisposal, TaxLot, Trade

Q=Decimal("0.01")
def m(v:Decimal)->Decimal:return v.quantize(Q,rounding=ROUND_HALF_UP)

def apply_trade(session:Session,trade:Trade)->dict:
    position=session.scalar(select(Position).where(Position.portfolio_id==trade.portfolio_id,Position.security_id==trade.security_id))
    if trade.side=="buy":
        total_cost=trade.quantity*trade.price+trade.fees
        if position:
            old_cost=position.quantity*position.average_cost
            position.quantity+=trade.quantity
            position.average_cost=(old_cost+total_cost)/position.quantity
        else:
            position=Position(portfolio_id=trade.portfolio_id,security_id=trade.security_id,quantity=trade.quantity,average_cost=total_cost/trade.quantity,current_price=trade.price);session.add(position)
        session.add(TaxLot(portfolio_id=trade.portfolio_id,security_id=trade.security_id,acquisition_date=trade.executed_at.date(),quantity_original=trade.quantity,quantity_remaining=trade.quantity,unit_cost=trade.price,fees=trade.fees,currency=trade.currency,fx_rate_at_acquisition=trade.fx_rate,source_ref=trade.id))
        session.flush()
        return {"realized_pnl":m(Decimal("0")),"quantity":str(position.quantity)}
    if not position or position.quantity<trade.quantity: raise ValueError("Insufficient position quantity")
    remaining=trade.quantity; realized=Decimal("0")
    lots=session.scalars(select(TaxLot).where(TaxLot.portfolio_id==trade.portfolio_id,TaxLot.security_id==trade.security_id,TaxLot.quantity_remaining>0).order_by(TaxLot.acquisition_date,TaxLot.id)).all()
    fee_per_unit=trade.fees/trade.quantity
    for lot in lots:
        if remaining<=0:break
        qty=min(remaining,lot.quantity_remaining)
        basis=qty*lot.unit_cost+(lot.fees*(qty/lot.quantity_original))
        proceeds=qty*trade.price-qty*fee_per_unit
        pnl=proceeds-basis
        lot.quantity_remaining-=qty;remaining-=qty;realized+=pnl
        session.add(LotDisposal(trade_id=trade.id,tax_lot_id=lot.id,quantity=qty,cost_basis=m(basis),realized_pnl=m(pnl),allocation_rule="FIFO"))
    if remaining>0:raise ValueError("Tax lots do not cover sale")
    position.quantity-=trade.quantity
    position.current_price=trade.price
    if position.quantity==0:position.average_cost=Decimal("0")
    session.flush()
    return {"realized_pnl":m(realized),"quantity":str(position.quantity)}

def portfolio_summary(session:Session,portfolio_id:str)->dict:
    positions=session.scalars(select(Position).where(Position.portfolio_id==portfolio_id)).all()
    total=Decimal("0");cost=Decimal("0");rows=[]
    for p in positions:
        price=p.current_price or p.average_cost;value=p.quantity*price;basis=p.quantity*p.average_cost;total+=value;cost+=basis
        rows.append({"security_id":p.security_id,"quantity":str(p.quantity),"average_cost":str(p.average_cost),"price":str(price),"value":str(m(value)),"unrealized_pnl":str(m(value-basis))})
    return {"market_value":str(m(total)),"cost_basis":str(m(cost)),"unrealized_pnl":str(m(total-cost)),"positions":rows}
