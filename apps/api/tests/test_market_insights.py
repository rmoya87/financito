from datetime import datetime,timedelta,timezone
from decimal import Decimal

from sqlalchemy import delete

from financito.db import SessionLocal
from financito.models import Security
from financito.models_extended import MarketPrice,NewsItem,TrackedAsset
from financito.models_analytics import NewsAnalysis
from financito.services import market_insights,news_analysis
from financito.services.market_insights import portfolio_market_insights
from financito.services.news_analysis import ingest_query


def test_news_rate_limit_returns_friendly_warning_and_keeps_local_flow(monkeypatch):
    monkeypatch.setattr(
        news_analysis.GdeltNewsProvider,
        "search",
        lambda self,query,limit=20: (_ for _ in ()).throw(
            RuntimeError("La fuente de noticias está limitando temporalmente las consultas.")
        ),
    )
    with SessionLocal() as db:
        result=ingest_query(db,"apple",30)
        assert result["inserted"]==0
        assert result["discovered"]==0
        assert result["warning"]=="La fuente de noticias está limitando temporalmente las consultas."
        assert "http" not in result["warning"].lower()


def test_market_insights_use_position_history_and_local_news_without_ai(monkeypatch):
    with SessionLocal() as db:
        security=Security(asset_class="stock",symbol="TSTI",name="Insight Test Corp",currency="EUR")
        db.add(security);db.flush()
        tracking=TrackedAsset(
            security_id=security.id,
            tracking_state="watching",
            preferred_currency="EUR",
        )
        db.add(tracking)
        now=datetime.now(timezone.utc)
        prices=[
            (now-timedelta(days=365),Decimal("100")),
            (now-timedelta(days=90),Decimal("110")),
            (now-timedelta(days=30),Decimal("120")),
            (now,Decimal("125")),
        ]
        for stamp,price in prices:
            db.add(MarketPrice(
                security_id=security.id,
                timestamp=stamp,
                close=price,
                currency="EUR",
                provider="test",
                fetched_at=now,
                is_delayed=False,
            ))
        news=NewsItem(
            canonical_url="https://example.test/insight-test",
            source="Test source",
            headline="Insight Test Corp reports results",
            published_at=now,
            reliability=Decimal("0.8"),
        )
        db.add(news);db.flush()
        news_analysis.analyze_item(db,news)
        db.commit()

        monkeypatch.setattr(market_insights,"local_ai_status",lambda:{"chat_ready":False})
        result=portfolio_market_insights(db,refresh_news=False)

        assert result["method"]=="deterministic"
        assert result["ai_available"] is False
        asset=next(item for item in result["assets"] if item["security_id"]==security.id)
        assert asset["security_id"]==security.id
        assert asset["position_type"]=="watching"
        assert asset["history"]["observations"]==4
        assert asset["history"]["return_365d"] is not None
        assert asset["news"][0]["headline"]=="Insight Test Corp reports results"
        guidance=next(item for item in result["guidance"] if item["security_id"]==security.id)
        assert guidance["orientation"]=="mantener_observacion"
        assert "órdenes automáticas" in result["notice"]

        db.execute(delete(NewsAnalysis).where(NewsAnalysis.news_item_id==news.id))
        db.delete(news)
        db.execute(delete(MarketPrice).where(MarketPrice.security_id==security.id))
        db.delete(tracking)
        db.delete(security)
        db.commit()
