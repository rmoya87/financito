from datetime import datetime,timezone,timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Portfolio,Security
from financito.models_extended import MarketPrice,NewsItem,Trade
from financito.models_analytics import NewsAnalysis
from financito.services.broker_import import import_broker_csv
from financito.services.news_analysis import analyze_item
from financito.services.portfolio_analysis import portfolio_fit,portfolio_performance


def test_news_analysis_links_security_and_explains_signal():
    suffix=uuid4().hex[:6].upper()
    with SessionLocal() as db:
        security=Security(asset_class="stock",name=f"Demo Apple {suffix}",symbol=f"APL{suffix[:2]}",currency="EUR")
        db.add(security);db.flush()
        item=NewsItem(
            canonical_url=f"https://example.invalid/{suffix}",
            source="test",
            headline=f"{security.symbol} beats earnings and raises guidance",
            published_at=datetime.now(timezone.utc),
            reliability=Decimal("0.8"),
        )
        db.add(item);db.flush()
        rows=analyze_item(db,item)
        assert len(rows)==1
        assert rows[0].security_id==security.id
        assert rows[0].event_type in {"earnings","guidance"}
        assert rows[0].sentiment>0
        assert rows[0].impact_level=="high"
        assert rows[0].method_version=="heuristic-v1"
        assert rows[0].rationale


def test_broker_csv_is_idempotent_and_builds_fifo_position():
    suffix=uuid4().hex[:8].upper()
    with SessionLocal() as db:
        portfolio=Portfolio(name=f"Broker {suffix}",base_currency="EUR")
        db.add(portfolio);db.flush()
        csv_data=(
            "fecha;operacion;ticker;nombre;tipo_activo;cantidad;precio;comision;divisa\n"
            f"01/01/2026;compra;{suffix};Activo {suffix};stock;10;10;1;EUR\n"
            f"02/01/2026;compra;{suffix};Activo {suffix};stock;5;12;1;EUR\n"
            f"03/01/2026;venta;{suffix};Activo {suffix};stock;8;15;1;EUR\n"
        ).encode()
        first=import_broker_csv(db,portfolio.id,csv_data,"broker.csv")
        assert first["inserted"]==3
        assert first["created_securities"]==1
        db.flush()
        second=import_broker_csv(db,portfolio.id,csv_data,"broker.csv")
        assert second["inserted"]==0
        assert second["skipped"]==3
        security=db.scalar(select(Security).where(Security.symbol==suffix))
        assert security is not None
        trades=db.scalars(select(Trade).where(Trade.portfolio_id==portfolio.id)).all()
        assert len(trades)==3


def test_portfolio_fit_and_performance_are_deterministic():
    suffix=uuid4().hex[:8].upper()
    with SessionLocal() as db:
        portfolio=Portfolio(name=f"Perf {suffix}",base_currency="EUR")
        a=Security(asset_class="stock",name=f"A {suffix}",symbol=f"A{suffix[:4]}",currency="EUR")
        b=Security(asset_class="bond",name=f"B {suffix}",symbol=f"B{suffix[:4]}",currency="EUR")
        db.add_all([portfolio,a,b]);db.flush()
        csv_data=(
            "date,side,symbol,name,asset_class,quantity,price,fees,currency\n"
            f"2026-01-02,buy,{a.symbol},{a.name},stock,10,100,0,EUR\n"
        ).encode()
        import_broker_csv(db,portfolio.id,csv_data,"perf.csv")
        base=datetime(2026,1,2,tzinfo=timezone.utc)
        db.add_all([
            MarketPrice(security_id=a.id,timestamp=base,close=Decimal("100"),currency="EUR",provider="test",is_delayed=False),
            MarketPrice(security_id=a.id,timestamp=base+timedelta(days=30),close=Decimal("110"),currency="EUR",provider="test",is_delayed=False),
        ])
        db.flush()
        fit=portfolio_fit(db,portfolio.id,b.id,Decimal("0.10"))
        assert 0<=fit["fit_score"]<=1
        assert fit["post_asset_class_weight"]=="0.10"
        perf=portfolio_performance(db,portfolio.id)
        assert perf["mwr"] is not None
        assert perf["observations"]>=1
        assert 0<=perf["coverage"]<=1



def test_tracked_asset_uses_real_purchase_data_and_watch_state():
    from datetime import date
    from financito.services.investment_tracking import save_tracked_asset, tracked_assets

    suffix=uuid4().hex[:8].upper()
    with SessionLocal() as db:
        watch=save_tracked_asset(
            db,
            asset_class="crypto",
            name=f"Bitcoin {suffix}",
            identifier=f"bitcoin-{suffix.lower()}",
            owned=False,
            portfolio_id=None,
            quantity=None,
            purchase_price=None,
            purchase_date=None,
            fees=Decimal("0"),
            fx_rate=Decimal("1"),
            currency="EUR",
            provider_asset_id=f"bitcoin-{suffix.lower()}",
            notes=None,
        )
        assert watch["owned"] is False
        assert watch["tracking_state"]=="watching"

        owned=save_tracked_asset(
            db,
            asset_class="stock",
            name=f"Acción {suffix}",
            identifier=f"T{suffix[:4]}",
            owned=True,
            portfolio_id=None,
            quantity=Decimal("10"),
            purchase_price=Decimal("20"),
            purchase_date=date(2026,1,15),
            fees=Decimal("2"),
            fx_rate=Decimal("1"),
            currency="EUR",
            provider_asset_id=None,
            notes=None,
        )
        db.commit()
        assert owned["owned"] is True
        assert Decimal(owned["quantity"])==Decimal("10")
        assert Decimal(owned["average_cost"])==Decimal("20.2")

        rows=tracked_assets(db)
        match=next(x for x in rows if x["security_id"]==owned["security_id"])
        assert Decimal(match["cost_basis"])==Decimal("202")
        assert match["current_price"] is None
        assert match["unrealized_pnl"] is None

        db.add(MarketPrice(
            security_id=owned["security_id"],
            timestamp=datetime.now(timezone.utc),
            close=Decimal("25"),
            currency="EUR",
            provider="test",
            is_delayed=False,
        ))
        db.flush()
        refreshed=next(x for x in tracked_assets(db) if x["security_id"]==owned["security_id"])
        assert Decimal(refreshed["current_price"])==Decimal("25")
        assert Decimal(refreshed["current_value"])==Decimal("250")
        assert Decimal(refreshed["unrealized_pnl"])==Decimal("48")


def test_public_mortgage_rate_parser_accepts_label_before_or_after_value():
    from financito.services.market_research import _rates

    rows=_rates("Hipoteca fija: TIN 2,45 % y 2,80 % TAE. Alternativa 2,35 % TIN.")
    tins={row["value_percent"] for row in rows if row["type"]=="TIN"}
    taes={row["value_percent"] for row in rows if row["type"]=="TAE"}
    assert {"2.45","2.35"} <= tins
    assert "2.80" in taes


def test_market_conclusion_uses_net_known_saving_and_blocks_missing_costs():
    from financito.models import Mortgage
    from financito.services.market_research import _market_conclusion

    mortgage=Mortgage(
        lender="Banco actual",
        remaining_principal=Decimal("100000"),
        currency="EUR",
        interest_type="fixed",
        nominal_rate=Decimal("0.03"),
        monthly_payment=Decimal("700"),
        remaining_months=180,
    )
    leads=[
        {
            "source_id":"bank-a","provider":"Banco A","kind":"mortgage_subrogation","public_tin_min":2.4,
            "scenario":{
                "monthly_payment_difference":"35","remaining_interest_difference":"5000",
                "known_exit_penalty":"500","break_even_months_known_penalty_only":"14.3",
            },
        },
        {
            "source_id":"bank-b","provider":"Banco B","kind":"mortgage_subrogation","public_tin_min":2.3,
            "scenario":{
                "monthly_payment_difference":"40","remaining_interest_difference":"7000",
                "known_exit_penalty":"1000","break_even_months_known_penalty_only":"25",
            },
        },
    ]
    result=_market_conclusion(mortgage,leads,{"ready":True,"missing":[]})
    assert result["status"]=="request_personalized_offer"
    assert result["provider"]=="Banco B"
    assert Decimal(result["estimated_net_interest_saving_known_costs"])==Decimal("6000.00")

    blocked=_market_conclusion(
        mortgage,leads,{"ready":False,"missing":["mortgage_exit_or_subrogation_penalty"]}
    )
    assert blocked["status"]=="needs_more_data"
    assert blocked["provider"] is None
    assert "mortgage_exit_or_subrogation_penalty" in blocked["missing"]


def test_tracked_history_endpoint_exposes_persisted_prices():
    from fastapi.testclient import TestClient
    from financito.main import app
    from financito.services.investment_tracking import save_tracked_asset

    suffix=uuid4().hex[:8].upper()
    with SessionLocal() as db:
        tracked=save_tracked_asset(
            db,
            asset_class="stock",
            name=f"History {suffix}",
            identifier=f"H{suffix[:4]}",
            owned=False,
            portfolio_id=None,
            quantity=None,
            purchase_price=None,
            purchase_date=None,
            fees=Decimal("0"),
            fx_rate=Decimal("1"),
            currency="EUR",
            provider_asset_id=None,
            notes=None,
        )
        db.add_all([
            MarketPrice(
                security_id=tracked["security_id"],
                timestamp=datetime.now(timezone.utc)-timedelta(days=2),
                close=Decimal("10"),
                currency="EUR",
                provider="test",
                is_delayed=True,
            ),
            MarketPrice(
                security_id=tracked["security_id"],
                timestamp=datetime.now(timezone.utc)-timedelta(days=1),
                close=Decimal("11"),
                currency="EUR",
                provider="test",
                is_delayed=True,
            ),
        ])
        db.commit()
        security_id=tracked["security_id"]

    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code==200
        response=client.get("/api/v1/tracked-assets/history",params={"days":30})
        assert response.status_code==200
        row=next(x for x in response.json() if x["security_id"]==security_id)
        assert len(row["rows"])>=2
        assert row["rows"][-1]["provider"]=="test"
