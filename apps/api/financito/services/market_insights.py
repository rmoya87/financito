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


def _fallback_risk(history_ctx:dict)->str:
    observations=int(history_ctx.get("observations") or 0)
    if observations<3:
        return "unknown"
    volatility=history_ctx.get("volatility")
    drawdown=history_ctx.get("max_drawdown")
    if (volatility is not None and float(volatility)>=0.45) or (drawdown is not None and float(drawdown)<=-0.30):
        return "elevated"
    if (volatility is not None and float(volatility)>=0.25) or (drawdown is not None and float(drawdown)<=-0.15):
        return "moderate"
    return "limited"


def _selected_news_fallback(contexts:list[dict],limit:int=6)->list[dict]:
    selected=[];seen=set()
    for asset in contexts:
        for item in asset.get("news") or []:
            news_id=str(item.get("id") or "")
            if not news_id or news_id in seen:
                continue
            seen.add(news_id)
            selected.append({
                "id":news_id,
                "headline":item.get("headline"),
                "source":item.get("source"),
                "published_at":item.get("published_at"),
                "url":item.get("url"),
                "reliability":item.get("reliability"),
                "linked_assets":[asset["name"]],
                "why_relevant":"Noticia vinculada a un activo seguido.",
            })
            if len(selected)>=limit:
                return selected
    return selected


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
    news_catalog={}
    for asset in assets:
        related=[]
        for item in news:
            matched=[a for a in item.get("analysis",[]) if a.get("security_id")==asset["security_id"]]
            if not matched:
                continue
            row={
                "id":item["id"],
                "headline":item["headline"],
                "source":item["source"],
                "published_at":str(item["published_at"]),
                "url":item["url"],
                "reliability":item.get("reliability"),
                "signals":[{
                    "event_type":signal.get("event_type"),
                    "sentiment":signal.get("sentiment"),
                    "impact_level":signal.get("impact_level"),
                    "confidence":signal.get("confidence"),
                    "rationale":signal.get("rationale"),
                } for signal in matched],
            }
            related.append(row)
            news_catalog[str(item["id"])]=row
            if len(related)>=12:
                break
        history_ctx=_asset_history_context(session,asset)
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
            "history":history_ctx,
            "news":related,
        })

    fallback_rows=[]
    for item in contexts:
        enough=item["history"]["observations"]>=3
        risk_level=_fallback_risk(item["history"])
        fallback_rows.append({
            "security_id":item["security_id"],
            "name":item["name"],
            "orientation":"mantener_observacion" if enough else "datos_insuficientes",
            "investment_status":"considerar_con_cautela" if enough and risk_level!="elevated" else ("riesgo_elevado" if risk_level=="elevated" else "datos_insuficientes"),
            "future_risk_level":risk_level,
            "summary":"Sin IA local, Financito no emite una conclusión de entrada; conserva histórico, riesgo y noticias estructuradas para revisión.",
            "reasons":[],
            "risks":[],
            "watch":[],
        })

    fallback_news=_selected_news_fallback(contexts)
    fallback={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "summary":"Análisis determinista preparado para tus activos guardados.",
        "assets":contexts,
        "guidance":fallback_rows,
        "news_digest":{
            "summary":"Selección limitada de noticias vinculadas a los activos seguidos.",
            "items":fallback_news,
            "risks":[],
            "watch":[],
            "selection_method":"deterministic_relevance",
        },
        "ai_available":False,
        "method":"deterministic",
        "news_refresh":news_refresh,
        "notice":"La conclusión indica si los datos bastan para considerar una inversión y qué riesgos conocidos merecen atención; no predice rentabilidad futura ni ejecuta compras o ventas.",
    }
    ai=local_ai_status()
    if not contexts or not ai.get("chat_ready"):
        fallback["ai_available"]=bool(ai.get("chat_ready"))
        return fallback

    prompt="""Eres el analista local de inversiones de Financito. Trabaja EXCLUSIVAMENTE con el JSON proporcionado.
Devuelve JSON con:
- summary: resumen de cartera en máximo 4 frases.
- guidance: un objeto por security_id con name, orientation, investment_status, future_risk_level, summary, reasons, risks y watch.
- news_digest: objeto con summary, selected_news_ids (máximo 6 IDs de noticias), risks y watch.

Valores permitidos:
orientation: estudiar_entrada, mantener_observacion, revisar_exposicion, datos_insuficientes.
investment_status: considerar, considerar_con_cautela, no_considerar_ahora, datos_insuficientes, riesgo_elevado.
future_risk_level: limited, moderate, elevated, unknown.

Criterios:
1. Combina valoración real o simulada, P&L, retorno histórico 30/90/365d, volatilidad/drawdown y noticias vinculadas.
2. Distingue claramente posición real, simulada y activo solo seguido.
3. investment_status responde si, con LOS DATOS DISPONIBLES, hay base suficiente para considerar una entrada. No es una orden de compra.
4. future_risk_level describe riesgos observables hacia delante basados en histórico/noticias; no es una predicción de precio.
5. Selecciona solo las noticias materialmente útiles para la decisión. No selecciones todas por defecto y no inventes IDs.
6. No inventes precios, objetivos, probabilidades, noticias ni fundamentos no incluidos.
7. No conviertas sentimiento de noticias en predicción. Explica contradicciones entre precio, histórico y noticias.
8. Máximo 3 reasons, 3 risks y 3 watch por activo; máximo 4 riesgos/watch en news_digest.
9. Si faltan histórico o noticias suficientes usa datos_insuficientes/unknown.

DATOS:
"""+json.dumps({"assets":contexts},ensure_ascii=False,default=str)
    try:
        generated=generate_json(prompt,timeout=240)
        raw_guidance=generated.get("guidance") if isinstance(generated.get("guidance"),list) else []
        by_id={str(item.get("security_id")):item for item in raw_guidance if isinstance(item,dict)}
        guidance=[]
        allowed_orientation={"estudiar_entrada","mantener_observacion","revisar_exposicion","datos_insuficientes"}
        allowed_status={"considerar","considerar_con_cautela","no_considerar_ahora","datos_insuficientes","riesgo_elevado"}
        allowed_risk={"limited","moderate","elevated","unknown"}
        for item in contexts:
            raw=by_id.get(item["security_id"],{})
            orientation=str(raw.get("orientation") or "datos_insuficientes")
            investment_status=str(raw.get("investment_status") or "datos_insuficientes")
            future_risk_level=str(raw.get("future_risk_level") or "unknown")
            if orientation not in allowed_orientation:
                orientation="datos_insuficientes"
            if investment_status not in allowed_status:
                investment_status="datos_insuficientes"
            if future_risk_level not in allowed_risk:
                future_risk_level="unknown"
            if item["history"]["observations"]<3:
                orientation="datos_insuficientes"
                investment_status="datos_insuficientes"
                future_risk_level="unknown"
            guidance.append({
                "security_id":item["security_id"],
                "name":item["name"],
                "orientation":orientation,
                "investment_status":investment_status,
                "future_risk_level":future_risk_level,
                "summary":str(raw.get("summary") or "No hay una conclusión local suficiente para este activo."),
                "reasons":[str(x) for x in (raw.get("reasons") or [])[:3]],
                "risks":[str(x) for x in (raw.get("risks") or [])[:3]],
                "watch":[str(x) for x in (raw.get("watch") or [])[:3]],
            })

        raw_digest=generated.get("news_digest") if isinstance(generated.get("news_digest"),dict) else {}
        requested_ids=[str(x) for x in (raw_digest.get("selected_news_ids") or [])[:6]]
        selected=[]
        for news_id in requested_ids:
            item=news_catalog.get(news_id)
            if item is None:
                continue
            linked_assets=[
                asset["name"] for asset in contexts
                if any(str(row.get("id"))==news_id for row in asset.get("news") or [])
            ]
            selected.append({
                "id":news_id,
                "headline":item["headline"],
                "source":item["source"],
                "published_at":item["published_at"],
                "url":item["url"],
                "reliability":item.get("reliability"),
                "linked_assets":linked_assets,
                "why_relevant":"Seleccionada por la IA local por su relevancia para los activos seguidos.",
            })
        if not selected:
            selected=fallback_news

        return {
            **fallback,
            "summary":str(generated.get("summary") or fallback["summary"]),
            "guidance":guidance,
            "news_digest":{
                "summary":str(raw_digest.get("summary") or fallback["news_digest"]["summary"]),
                "items":selected,
                "risks":[str(x) for x in (raw_digest.get("risks") or [])[:4]],
                "watch":[str(x) for x in (raw_digest.get("watch") or [])[:4]],
                "selection_method":"local_ai",
            },
            "ai_available":True,
            "method":"local_ai",
        }
    except Exception:
        fallback["ai_available"]=True
        fallback["summary"]="La IA local no pudo cerrar el resumen; se mantienen disponibles los datos deterministas de valoración, histórico y una selección limitada de noticias."
        return fallback
