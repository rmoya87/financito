from __future__ import annotations

from datetime import datetime,timedelta,timezone
import json

from sqlalchemy.orm import Session

from ..domain.risk import risk_metrics
from .investment_tracking import tracked_assets
from .local_ai import generate_json,status as local_ai_status
from .market_data import history
from .news_analysis import analyze_all,ingest_query,local_news


def _period_return(rows:list[dict],days:int)->float|None:
    if len(rows)<2:
        return None
    normalized=[]
    for row in rows:
        stamp=row["timestamp"]
        if stamp.tzinfo is None:
            stamp=stamp.replace(tzinfo=timezone.utc)
        normalized.append((stamp,float(row["close"])))
    normalized.sort(key=lambda item:item[0])
    latest_stamp,latest=normalized[-1]
    cutoff=latest_stamp-timedelta(days=days)
    candidates=[item for item in normalized if item[0]>=cutoff]
    first=(candidates[0] if candidates else normalized[0])[1]
    if first==0:
        return None
    return latest/first-1


def _asset_history_context(session:Session,asset:dict)->dict:
    rows=history(session,asset["security_id"])
    prices=[float(row["close"]) for row in rows]
    periods=365 if asset.get("asset_class")=="crypto" else 252
    metrics=risk_metrics(prices,periods_per_year=periods)
    return {
        "observations":len(rows),
        "return_30d":_period_return(rows,30),
        "return_90d":_period_return(rows,90),
        "return_365d":_period_return(rows,365),
        "volatility":metrics.get("volatility"),
        "max_drawdown":metrics.get("max_drawdown"),
        "sharpe":metrics.get("sharpe"),
        "last_history_date":None if not rows else str(rows[-1]["timestamp"]),
        "providers":sorted({str(row["provider"]) for row in rows}),
    }


def portfolio_market_insights(session:Session,refresh_news:bool=True)->dict:
    assets=tracked_assets(session)
    news_refresh={"inserted":0,"discovered":0,"warning":None}
    if refresh_news and assets:
        terms=[]
        for asset in assets[:8]:
            value=(asset.get("identifier") or asset.get("name") or "").strip()
            if value and value not in terms:
                terms.append(value)
        if terms:
            news_refresh=ingest_query(session," OR ".join(terms),30)
            analyze_all(session,300)

    news=local_news(session,120)
    contexts=[]
    for asset in assets:
        related=[]
        for item in news:
            matched=[a for a in item.get("analysis",[]) if a.get("security_id")==asset["security_id"]]
            if not matched:
                continue
            related.append({
                "headline":item["headline"],
                "source":item["source"],
                "published_at":str(item["published_at"]),
                "url":item["url"],
                "signals":[{
                    "event_type":row.get("event_type"),
                    "sentiment":row.get("sentiment"),
                    "impact_level":row.get("impact_level"),
                    "confidence":row.get("confidence"),
                    "rationale":row.get("rationale"),
                } for row in matched],
            })
            if len(related)>=8:
                break
        contexts.append({
            "security_id":asset["security_id"],
            "name":asset["name"],
            "identifier":asset.get("identifier"),
            "asset_class":asset["asset_class"],
            "position_type":"owned" if asset["owned"] else ("simulated" if asset.get("simulation") else "watching"),
            "owned":asset["owned"],
            "current_price":asset.get("current_price"),
            "cost_basis":asset.get("cost_basis"),
            "current_value":asset.get("current_value"),
            "unrealized_pnl":asset.get("unrealized_pnl"),
            "unrealized_return":asset.get("unrealized_return"),
            "realized_pnl":asset.get("realized_pnl"),
            "dividends":asset.get("dividends"),
            "simulation":asset.get("simulation"),
            "price_provider":asset.get("price_provider"),
            "price_as_of":asset.get("price_as_of"),
            "history":_asset_history_context(session,asset),
            "news":related,
        })

    fallback_rows=[{
        "security_id":item["security_id"],
        "name":item["name"],
        "orientation":"datos_insuficientes" if item["history"]["observations"]<3 else "mantener_observacion",
        "summary":"No hay IA local disponible; se muestran únicamente valoración, histórico y noticias estructuradas.",
        "reasons":[],
        "risks":[],
        "watch":[],
    } for item in contexts]
    fallback={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "summary":"Análisis determinista preparado para tus activos guardados.",
        "assets":contexts,
        "guidance":fallback_rows,
        "ai_available":False,
        "method":"deterministic",
        "news_refresh":news_refresh,
        "notice":"Estas orientaciones sirven para revisar una decisión; no son órdenes automáticas de compra o venta ni predicciones de rentabilidad.",
    }
    ai=local_ai_status()
    if not contexts or not ai.get("chat_ready"):
        fallback["ai_available"]=bool(ai.get("chat_ready"))
        return fallback

    prompt="""Eres el analista local de inversiones de Financito. Trabaja EXCLUSIVAMENTE con el JSON proporcionado.
Devuelve JSON con:
- summary: resumen de cartera en máximo 4 frases.
- guidance: un objeto por security_id con name, orientation, summary, reasons, risks y watch.
orientation solo puede ser: estudiar_entrada, mantener_observacion, revisar_exposicion, datos_insuficientes.

Criterios:
1. Combina valoración real o simulada, P&L, retorno histórico 30/90/365d, volatilidad/drawdown y noticias vinculadas.
2. Distingue claramente posición real, simulada y activo solo seguido.
3. "estudiar_entrada" significa que hay señales suficientes para estudiar una entrada, NO una orden de compra.
4. "revisar_exposicion" significa revisar si el tamaño/riesgo sigue encajando, NO una orden de venta.
5. No inventes precios, objetivos, probabilidades, noticias ni fundamentos no incluidos.
6. No conviertas sentimiento de noticias en predicción. Explica contradicciones entre precio, histórico y noticias.
7. Máximo 3 reasons, 3 risks y 3 watch por activo. Frases cortas y accionables.
8. Si faltan histórico o noticias suficientes usa datos_insuficientes.

DATOS:
"""+json.dumps({"assets":contexts},ensure_ascii=False,default=str)
    try:
        generated=generate_json(prompt,timeout=240)
        raw_guidance=generated.get("guidance") if isinstance(generated.get("guidance"),list) else []
        by_id={str(item.get("security_id")):item for item in raw_guidance if isinstance(item,dict)}
        guidance=[]
        allowed={"estudiar_entrada","mantener_observacion","revisar_exposicion","datos_insuficientes"}
        for item in contexts:
            raw=by_id.get(item["security_id"],{})
            orientation=str(raw.get("orientation") or "datos_insuficientes")
            if orientation not in allowed:
                orientation="datos_insuficientes"
            guidance.append({
                "security_id":item["security_id"],
                "name":item["name"],
                "orientation":orientation,
                "summary":str(raw.get("summary") or "No hay una conclusión local suficiente para este activo."),
                "reasons":[str(x) for x in (raw.get("reasons") or [])[:3]],
                "risks":[str(x) for x in (raw.get("risks") or [])[:3]],
                "watch":[str(x) for x in (raw.get("watch") or [])[:3]],
            })
        return {
            **fallback,
            "summary":str(generated.get("summary") or fallback["summary"]),
            "guidance":guidance,
            "ai_available":True,
            "method":"local_ai",
        }
    except Exception:
        fallback["ai_available"]=True
        fallback["summary"]="La IA local no pudo cerrar el resumen; se mantienen disponibles los datos deterministas de valoración, histórico y noticias."
        return fallback
