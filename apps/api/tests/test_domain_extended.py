from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select

from financito.config import settings
from financito.db import SessionLocal
from financito.domain.backtest import backtest_ma, amortize_vs_invest
from financito.domain.portfolio import apply_trade
from financito.domain.stress import run_stress
from financito.models import Account, Category, Portfolio, Security, Transaction
from financito.models_extended import LotDisposal, TaxLot, Trade
from financito.models_analytics import TransactionRule
from financito.services.categorization import ensure_categories
from financito.services.documents import index_document
from financito.services.rag import search
from financito.services.transaction_ops import detect_internal_transfers, set_splits


def test_fifo_tax_lots_realized_pnl():
    with SessionLocal() as db:
        p=Portfolio(name="FIFO"); s=Security(asset_class="stock",name="Demo SA",symbol="DME",currency="EUR")
        db.add_all([p,s]);db.flush()
        b1=Trade(portfolio_id=p.id,security_id=s.id,side="buy",quantity=Decimal("10"),price=Decimal("10"),fees=Decimal("0"),currency="EUR",fx_rate=Decimal("1"),executed_at=datetime(2025,1,1,tzinfo=timezone.utc))
        db.add(b1);db.flush();apply_trade(db,b1)
        b2=Trade(portfolio_id=p.id,security_id=s.id,side="buy",quantity=Decimal("10"),price=Decimal("20"),fees=Decimal("0"),currency="EUR",fx_rate=Decimal("1"),executed_at=datetime(2025,2,1,tzinfo=timezone.utc))
        db.add(b2);db.flush();apply_trade(db,b2)
        sale=Trade(portfolio_id=p.id,security_id=s.id,side="sell",quantity=Decimal("15"),price=Decimal("30"),fees=Decimal("0"),currency="EUR",fx_rate=Decimal("1"),executed_at=datetime(2025,3,1,tzinfo=timezone.utc))
        db.add(sale);db.flush();result=apply_trade(db,sale);db.commit()
        assert result["realized_pnl"] == Decimal("250.00")
        lots=db.scalars(select(TaxLot).where(TaxLot.portfolio_id==p.id).order_by(TaxLot.acquisition_date)).all()
        assert lots[0].quantity_remaining == 0
        assert lots[1].quantity_remaining == 5
        assert len(db.scalars(select(LotDisposal).where(LotDisposal.trade_id==sale.id)).all()) == 2


def test_transfer_matching_and_exact_splits():
    with SessionLocal() as db:
        categories=ensure_categories(db)
        a=Account(name="A");b=Account(name="B");db.add_all([a,b]);db.flush()
        day=date(2026,1,10)
        t1=Transaction(account_id=a.id,booking_date=day,amount=Decimal("-500"),base_amount=Decimal("-500"),currency="EUR",base_currency="EUR",description_raw="Transfer",description_normalized="transfer",duplicate_fingerprint="transfer-a")
        t2=Transaction(account_id=b.id,booking_date=day+timedelta(days=1),amount=Decimal("500"),base_amount=Decimal("500"),currency="EUR",base_currency="EUR",description_raw="Transfer",description_normalized="transfer",duplicate_fingerprint="transfer-b")
        db.add_all([t1,t2]);db.flush()
        assert detect_internal_transfers(db) == 1
        assert t1.is_internal_transfer and t2.is_internal_transfer
        rows=set_splits(db,t1.id,[{"amount":"300","category_id":categories["housing"].id},{"amount":"200","category_id":categories["other"].id}])
        assert sum((r.amount for r in rows),Decimal("0")) == Decimal("500")


def test_rule_priority_before_classifier():
    with SessionLocal() as db:
        categories=ensure_categories(db)
        db.add(TransactionRule(priority=1,matcher_type="contains",matcher_value="cafeteria especial",category_id=categories["shopping"].id,enabled=True));db.flush()
        from financito.services.categorization import categorize_transaction
        a=Account(name="Rules");db.add(a);db.flush()
        tx=Transaction(account_id=a.id,booking_date=date.today(),amount=Decimal("-9"),base_amount=Decimal("-9"),currency="EUR",base_currency="EUR",description_raw="CAFETERIA ESPECIAL",description_normalized="cafeteria especial",duplicate_fingerprint="rule-priority")
        categorize_transaction(db,tx)
        assert tx.category_id == categories["shopping"].id
        assert tx.categorization_method == "rule"


def test_rag_indexes_and_finds_vault_text():
    path=settings.vault_dir/"rag-test.txt"
    path.write_text("La póliza Demo exige un preaviso de 30 días para cancelar.",encoding="utf-8")
    with SessionLocal() as db:
        indexed=index_document(db,str(path),"insurance");db.commit()
        assert indexed.chunks_created >= 1
        results=search(db,"preaviso cancelar",5)
        assert any(r["document_id"]==indexed.document.id for r in results)


def test_stress_backtest_and_planning_engines():
    stressed=run_stress(Decimal("10000"),Decimal("3000"),Decimal("2500"),Decimal("20000"),Decimal("50"),Decimal("2000"),Decimal("20"),6)
    assert Decimal(stressed["ending_liquidity"]) < Decimal("10000")
    prices=[100+i*.2+(3 if i%7==0 else 0) for i in range(160)]
    bt=backtest_ma(prices,10,30,5)
    assert bt["observations"] > 0
    scenario=amortize_vs_invest(10000,.03,.05,10,.19)
    assert "difference_invest_minus_amortize" in scenario
