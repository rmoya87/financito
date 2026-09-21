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
        assert guidance["investment_status"] in {"considerar_con_cautela","riesgo_elevado"}
        assert guidance["future_risk_level"] in {"limited","moderate","elevated"}
        assert len(result["news_digest"]["items"])<=6
        assert result["news_digest"]["items"][0]["id"]==news.id
        assert "no predice rentabilidad futura" in result["notice"]

        db.execute(delete(NewsAnalysis).where(NewsAnalysis.news_item_id==news.id))
        db.delete(news)
        db.execute(delete(MarketPrice).where(MarketPrice.security_id==security.id))
        db.delete(tracking)
        db.delete(security)
        db.commit()


def test_market_insights_ai_selects_news_and_reports_investment_basis_and_future_risk(monkeypatch):
    with SessionLocal() as db:
        security=Security(asset_class="stock",symbol="AITS",name="AI Selection Test",currency="EUR")
        db.add(security);db.flush()
        tracking=TrackedAsset(security_id=security.id,tracking_state="watching",preferred_currency="EUR")
        db.add(tracking)
        now=datetime.now(timezone.utc)
        for days,price in ((365,"100"),(90,"103"),(30,"106"),(0,"108")):
            db.add(MarketPrice(
                security_id=security.id,
                timestamp=now-timedelta(days=days),
                close=Decimal(price),
                currency="EUR",
                provider="test",
                fetched_at=now,
                is_delayed=False,
            ))
        news=NewsItem(
            canonical_url="https://example.test/ai-selection",
            source="Selected source",
            headline="AI Selection Test announces material update",
            published_at=now,
            reliability=Decimal("0.9"),
        )
        db.add(news);db.flush()
        db.add(NewsAnalysis(
            news_item_id=news.id,
            security_id=security.id,
            event_type="results",
            sentiment=Decimal("0.1"),
            impact_level="medium",
            confidence=Decimal("0.9"),
            method_version="test",
            rationale="Material update",
        ))
        db.commit()

        monkeypatch.setattr(market_insights,"local_ai_status",lambda:{"chat_ready":True})
        monkeypatch.setattr(market_insights,"generate_json",lambda prompt,timeout=240:{
            "summary":"Hay datos suficientes para una revisión informada.",
            "guidance":[{
                "security_id":security.id,
                "name":security.name,
                "orientation":"estudiar_entrada",
                "investment_status":"considerar_con_cautela",
                "future_risk_level":"moderate",
                "summary":"El histórico y la noticia permiten considerar la entrada con cautela.",
                "reasons":["Histórico disponible","Noticia material vinculada"],
                "risks":["Volatilidad y reacción a la noticia"],
                "watch":["Evolución posterior al anuncio"],
            }],
            "news_digest":{
                "summary":"Solo se conserva la noticia material.",
                "selected_news_ids":[news.id],
                "risks":["Reacción adversa al anuncio"],
                "watch":["Confirmación en precio"],
            },
        })

        result=portfolio_market_insights(db,refresh_news=False)
        guidance=next(item for item in result["guidance"] if item["security_id"]==security.id)
        assert result["method"]=="local_ai"
        assert guidance["investment_status"]=="considerar_con_cautela"
        assert guidance["future_risk_level"]=="moderate"
        assert result["news_digest"]["selection_method"]=="local_ai"
        assert [item["id"] for item in result["news_digest"]["items"]]==[news.id]
        assert result["news_digest"]["risks"]==["Reacción adversa al anuncio"]

        db.execute(delete(NewsAnalysis).where(NewsAnalysis.news_item_id==news.id))
        db.delete(news)
        db.execute(delete(MarketPrice).where(MarketPrice.security_id==security.id))
        db.delete(tracking)
        db.delete(security)
        db.commit()
