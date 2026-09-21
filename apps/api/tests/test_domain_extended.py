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


def test_rag_lexical_search_can_skip_vector_model(monkeypatch):
    path=settings.vault_dir/"rag-lexical-fast.txt"
    path.write_text("La póliza rápida tiene una franquicia de 250 euros.",encoding="utf-8")
    with SessionLocal() as db:
        indexed=index_document(db,str(path),"insurance");db.commit()
        def should_not_embed(*args,**kwargs):
            raise AssertionError("La búsqueda lexical no debe invocar Ollama")
        monkeypatch.setattr("financito.services.rag.embed",should_not_embed)
        results=search(db,"franquicia 250",5,use_vector=False)
        assert any(r["document_id"]==indexed.document.id for r in results)


def test_stress_backtest_and_planning_engines():
    stressed=run_stress(Decimal("10000"),Decimal("3000"),Decimal("2500"),Decimal("20000"),Decimal("50"),Decimal("2000"),Decimal("20"),6)
    assert Decimal(stressed["ending_liquidity"]) < Decimal("10000")
    prices=[100+i*.2+(3 if i%7==0 else 0) for i in range(160)]
    bt=backtest_ma(prices,10,30,5)
    assert bt["observations"] > 0
    scenario=amortize_vs_invest(10000,.03,.05,10,.19)
    assert "difference_invest_minus_amortize" in scenario


def test_tax_estimate_uses_versioned_spanish_rules():
    from financito.services.tax import estimate,upsert_profile
    from financito.db import SessionLocal
    with SessionLocal() as db:
        upsert_profile(db,{
            "jurisdiction":"ES","tax_year":2026,"autonomous_community":"Madrid","filing_status":"individual",
            "adults":1,"dependent_children":0,"children_under_three":0,"primary_residence":True,
            "employment_income":Decimal("40000"),"social_security_contributions":Decimal("2500"),
            "employment_deductible_expenses":Decimal("2000"),"tax_withholdings":Decimal("7000"),
            "interest_income":Decimal("1000"),"other_general_income":Decimal("0"),
            "carried_forward_savings_losses":Decimal("0"),"pension_contributions":Decimal("0"),
        })
        db.flush()
        result=estimate(db,"ES",2026)
        assert result["rules_version"]=="es-irpf-2026-v1"
        assert result["calculation"]["regional_rules_supported"] is True
        assert Decimal(result["calculation"]["savings_tax"])==Decimal("190.00")
        assert result["calculation"]["estimated_total_tax"] is not None
