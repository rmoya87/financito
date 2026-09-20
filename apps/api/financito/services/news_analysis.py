from __future__ import annotations

import json
import re
from decimal import Decimal

from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..models import Security
from ..models_extended import NewsItem
from ..models_analytics import NewsAnalysis
from .investment_tracking import tracked_assets
from .local_ai import generate_json,status as local_ai_status

METHOD_VERSION="heuristic-v1"

POSITIVE={
    "beat","beats","record profit","record revenue","raises guidance","raised guidance","upgrade","upgraded",
    "dividend increase","buyback","approval","approved","strong growth","profit rises","revenue rises",
    "supera previsiones","beneficio récord","beneficio record","sube previsiones","mejora previsiones","recompra","aprobado","crece"
}
NEGATIVE={
    "miss","misses","cut guidance","cuts guidance","downgrade","downgraded","lawsuit","probe","investigation",
    "recall","loss widens","bankruptcy","default","fraud","warning","profit falls","revenue falls",
    "incumple previsiones","rebaja previsiones","demanda","investigación","investigacion","retirada","quiebra","fraude","cae beneficio"
}
EVENTS=[
    ("bankruptcy",("bankruptcy","chapter 11","quiebra","concurso de acreedores")),
    ("merger_acquisition",("acquisition","acquire","merger","takeover","adquisición","adquisicion","fusión","fusion","opa")),
    ("earnings",("earnings","results","revenue","profit","eps","resultados","ingresos","beneficio")),
    ("guidance",("guidance","outlook","previsiones","perspectivas")),
    ("regulatory",("regulator","investigation","probe","antitrust","sec charges","regulador","investigación","investigacion","competencia")),
    ("legal",("lawsuit","court","settlement","demanda","tribunal","acuerdo judicial")),
    ("capital_return",("dividend","buyback","repurchase","dividendo","recompra")),
    ("capital_raise",("offering","share issue","rights issue","ampliación","ampliacion de capital")),
    ("product",("launch","approval","recall","producto","lanzamiento","aprobación","aprobacion","retirada")),
]

def _norm(value:str)->str:
    return re.sub(r"\s+"," ",(value or "").strip().lower())

def _matched(text:str,keywords)->list[str]:
    return sorted(k for k in keywords if k in text)

def _entity_matches(headline:str,securities:list[Security])->list[Security]:
    low=_norm(headline)
    out=[]
    for security in securities:
        symbol=(security.symbol or "").strip()
        name=_norm(security.name)
        symbol_match=False
        if symbol:
            escaped=re.escape(symbol)
            if len(symbol)>=3:
                symbol_match=bool(re.search(r"(?<![A-Za-z0-9])\$?"+escaped+r"(?![A-Za-z0-9])",headline,re.I))
            else:
                symbol_match=bool(re.search(r"\$"+escaped+r"\b",headline,re.I))
        name_match=len(name)>=5 and name in low
        if symbol_match or name_match:
            out.append(security)
    return out

def analyze_item(session:Session,item:NewsItem)->list[NewsAnalysis]:
    text=_norm(item.headline+" "+(item.summary or ""))
    positive=_matched(text,POSITIVE)
    negative=_matched(text,NEGATIVE)
    raw=len(positive)-len(negative)
    sentiment=Decimal(str(max(-1.0,min(1.0,raw/max(1,len(positive)+len(negative))))))
    event_type="general"
    event_hits=[]
    for event,keywords in EVENTS:
        hits=_matched(text,keywords)
        if hits:
            event_type=event
            event_hits=hits
            break
    impact_level="high" if event_type in {"bankruptcy","merger_acquisition","earnings","guidance","regulatory","capital_raise"} else ("medium" if event_type in {"legal","capital_return","product"} else "low")
    securities=session.scalars(select(Security)).all()
    linked=_entity_matches(item.headline,securities)
    session.execute(delete(NewsAnalysis).where(NewsAnalysis.news_item_id==item.id,NewsAnalysis.method_version==METHOD_VERSION))
    confidence=Decimal("0.50")
    if linked:confidence+=Decimal("0.20")
    if positive or negative:confidence+=Decimal("0.10")
    if event_hits:confidence+=Decimal("0.10")
    confidence=min(Decimal("0.90"),confidence)
    signals=["+"+k for k in positive]+["-"+k for k in negative]+["evento:"+k for k in event_hits]
    rationale=", ".join(signals) or "sin señales léxicas fuertes"
    rows=[]
    targets=linked or [None]
    for security in targets:
        row=NewsAnalysis(
            news_item_id=item.id,
            security_id=None if security is None else security.id,
            event_type=event_type,
            sentiment=sentiment,
            impact_level=impact_level,
            confidence=confidence,
            method_version=METHOD_VERSION,
            rationale=rationale[:1000],
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows

def analyze_all(session:Session,limit:int=500)->dict:
    items=session.scalars(select(NewsItem).order_by(NewsItem.published_at.desc()).limit(max(1,min(limit,2000)))).all()
    analyses=0
    for item in items:
        analyses+=len(analyze_item(session,item))
    return {"items":len(items),"analyses":analyses,"method_version":METHOD_VERSION}

def local_news(session:Session,limit:int=100)->list[dict]:
    items=session.scalars(select(NewsItem).order_by(NewsItem.published_at.desc()).limit(max(1,min(limit,500)))).all()
    ids=[x.id for x in items]
    analyses=session.scalars(select(NewsAnalysis).where(NewsAnalysis.news_item_id.in_(ids))).all() if ids else []
    security_ids=[a.security_id for a in analyses if a.security_id]
    securities={s.id:s for s in session.scalars(select(Security).where(Security.id.in_(security_ids))).all()} if security_ids else {}
    by_item={}
    for a in analyses:
        security=securities.get(a.security_id) if a.security_id else None
        by_item.setdefault(a.news_item_id,[]).append({
            "security_id":a.security_id,
            "security":None if security is None else security.name,
            "event_type":a.event_type,
            "sentiment":float(a.sentiment),
            "impact_level":a.impact_level,
            "confidence":float(a.confidence),
            "method_version":a.method_version,
            "rationale":a.rationale,
        })
    return [{
        "id":item.id,
        "headline":item.headline,
        "url":item.canonical_url,
        "source":item.source,
        "published_at":item.published_at,
        "reliability":float(item.reliability),
        "analysis":by_item.get(item.id,[]),
    } for item in items]


def portfolio_news_brief(session:Session,query:str|None=None,limit:int=25)->dict:
    items=local_news(session,limit)
    if query:
        terms=[x for x in _norm(query).split() if len(x)>2]
        filtered=[item for item in items if any(term in _norm(item["headline"]) for term in terms)]
        if filtered:items=filtered
    assets=tracked_assets(session)
    facts=[]
    for item in items[:15]:
        analyses=item.get("analysis") or []
        facts.append({
            "headline":item["headline"],"source":item["source"],"published_at":str(item["published_at"]),"url":item["url"],
            "linked_assets":[a.get("security") for a in analyses if a.get("security")],
            "event_types":sorted({a.get("event_type") for a in analyses if a.get("event_type")}),
            "impact_levels":sorted({a.get("impact_level") for a in analyses if a.get("impact_level")}),
        })
    holdings=[{
        "name":a["name"],"identifier":a.get("identifier"),"asset_class":a["asset_class"],"owned":a["owned"],
        "simulated":a.get("simulation") is not None,
    } for a in assets]

    fallback={
        "summary":"No hay suficientes noticias locales relacionadas con tus activos para elaborar un análisis." if not facts else f"Se han encontrado {len(facts)} noticias recientes para contextualizar frente a {len(holdings)} activos guardados.",
        "facts":facts,
        "portfolio_impacts":[],
        "risks":["El impacto de una noticia no permite predecir por sí solo la evolución del precio."],
        "watch":["Contrasta los hechos con la fuente original y revisa concentración, horizonte y liquidez antes de tomar una decisión."],
        "method":"deterministic_fallback",
        "ai_available":False,
    }
    ai=local_ai_status()
    if not facts or not ai.get("chat_ready"):
        fallback["ai_available"]=bool(ai.get("chat_ready"))
        return fallback
    prompt="""Eres el analista local de Financito. Trabaja SOLO con el JSON de hechos y activos incluido abajo.
Devuelve JSON con las claves summary (string), portfolio_impacts (array de objetos con asset, observation, possible_effects, evidence_headlines), risks (array de strings) y watch (array de strings).
Reglas: separa hechos de interpretación; no inventes información, precios, probabilidades ni recomendaciones de comprar/vender; usa lenguaje condicional para efectos futuros; menciona concentración o exposición solo si está respaldada por los activos; no conviertas sentimiento léxico en predicción. Si una noticia no afecta claramente a un activo, dilo.
DATOS:
"""+json.dumps({"query":query,"facts":facts,"assets":holdings},ensure_ascii=False,default=str)
    try:
        generated=generate_json(prompt)
        return {
            "summary":str(generated.get("summary") or fallback["summary"]),
            "facts":facts,
            "portfolio_impacts":generated.get("portfolio_impacts") if isinstance(generated.get("portfolio_impacts"),list) else [],
            "risks":generated.get("risks") if isinstance(generated.get("risks"),list) else fallback["risks"],
            "watch":generated.get("watch") if isinstance(generated.get("watch"),list) else fallback["watch"],
            "method":"local_ai",
            "ai_available":True,
        }
    except Exception as exc:
        fallback["ai_available"]=True
        fallback["ai_warning"]="La IA local no pudo completar el análisis; se muestran únicamente hechos estructurados."
        return fallback
