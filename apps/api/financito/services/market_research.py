from __future__ import annotations

from datetime import datetime, timezone
import html
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Mortgage


SOURCES = (
    {
        "id": "bankinter_novation",
        "provider": "Bankinter",
        "kind": "mortgage_current_bank",
        "url": "https://www.bankinter.com/banca/preguntas-frecuentes/hipotecas/es-posible-cambiar-las-condiciones-de-una-hipoteca",
    },
    {
        "id": "santander_subrogation",
        "provider": "Santander",
        "kind": "mortgage_subrogation",
        "url": "https://www.bancosantander.es/particulares/hipotecas/cambiar-hipoteca-banco",
    },
    {
        "id": "santander_fixed",
        "provider": "Santander",
        "kind": "mortgage_public_benchmark",
        "url": "https://www.bancosantander.es/particulares/hipotecas/hipoteca-fija",
    },
    {
        "id": "bbva_subrogation",
        "provider": "BBVA",
        "kind": "mortgage_subrogation",
        "url": "https://www.bbva.es/personas/productos/hipotecas/subrogacion-hipotecas.html",
    },
    {
        "id": "ing_subrogation",
        "provider": "ING",
        "kind": "mortgage_subrogation",
        "url": "https://www.ing.es/hipotecas/cambiar-hipoteca-banco",
    },
    {
        "id": "openbank_fixed",
        "provider": "Openbank",
        "kind": "mortgage_public_benchmark",
        "url": "https://www.openbank.es/hipoteca-fija",
    },
    {
        "id": "linea_directa_home",
        "provider": "Línea Directa",
        "kind": "home_insurance",
        "url": "https://www.lineadirecta.com/seguros-hogar",
    },
    {
        "id": "mapfre_home",
        "provider": "MAPFRE",
        "kind": "home_insurance",
        "url": "https://www.mapfre.es/particulares/seguros-de-hogar/",
    },
    {
        "id": "allianz_home",
        "provider": "Allianz",
        "kind": "home_insurance",
        "url": "https://www.allianz.es/seguro-de-hogar.html",
    },
    {
        "id": "axa_home",
        "provider": "AXA",
        "kind": "home_insurance",
        "url": "https://www.axa.es/es",
    },
    {
        "id": "mapfre_life_mortgage",
        "provider": "MAPFRE",
        "kind": "mortgage_life_insurance",
        "url": "https://www.mapfre.es/particulares/seguros-de-vida/seguro-amortizacion-hipoteca/",
    },
    {
        "id": "allianz_life_financial",
        "provider": "Allianz",
        "kind": "mortgage_life_insurance",
        "url": "https://www.allianz.es/seguros-vida/seguro-vida-proteccion-financiera.html",
    },
    {
        "id": "axa_life",
        "provider": "AXA",
        "kind": "life_insurance",
        "url": "https://www.axa.es/es",
    },
)


def _plain_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _rates(text: str) -> list[dict]:
    found = []
    for label, pattern in (
        ("TIN", r"(\d{1,2}(?:[\.,]\d{1,3})?)\s*%\s*TIN"),
        ("TAE", r"(\d{1,2}(?:[\.,]\d{1,3})?)\s*%\s*TAE(?:\s+Variable)?"),
    ):
        seen = set()
        for match in re.finditer(pattern, text, re.I):
            value = match.group(1).replace(",", ".")
            if value in seen:
                continue
            seen.add(value)
            found.append({"type": label, "value_percent": value})
            if len(seen) >= 5:
                break
    return found


def _claims(text: str) -> list[str]:
    checks = (
        ("subrogation", r"subrogaci[oó]n|cambiar tu hipoteca|traer mi hipoteca|trae tu hipoteca"),
        ("no_opening_fee", r"sin comisi[oó]n de apertura"),
        ("no_partial_prepayment_fee", r"sin comisi[oó]n.{0,50}amortizaci[oó]n (?:anticipada )?parcial"),
        ("linked_home_insurance", r"seguro de hogar"),
        ("linked_life_insurance", r"seguro de vida"),
        ("salary_link", r"domicili(?:ar|aci[oó]n).{0,40}n[oó]mina"),
        ("personalized_quote", r"precio personalizado|estudio personalizado|oferta vinculante|sujeta a aprobaci[oó]n"),
        ("home_insurance_discount", r"(?:\d{1,2})\s*%\s+menos.{0,80}seguro de hogar"),
    )
    return [key for key, pattern in checks if re.search(pattern, text, re.I)]


def _promo_percent(text: str) -> str | None:
    match = re.search(r"(\d{1,2})\s*%\s+(?:menos|de descuento).{0,120}seguro de hogar", text, re.I)
    return match.group(1) if match else None


def _scan_source(source: dict, client: httpx.Client) -> dict:
    try:
        response = client.get(source["url"])
        response.raise_for_status()
        text = _plain_text(response.text)
        return {
            **source,
            "status": "ok",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "rates": _rates(text),
            "claims": _claims(text),
            "promo_percent": _promo_percent(text),
            "requires_personalized_quote": True,
        }
    except Exception as exc:
        return {
            **source,
            "status": "unavailable",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "rates": [],
            "claims": [],
            "promo_percent": None,
            "requires_personalized_quote": True,
            "error": str(exc)[:240],
        }


def scan_public_market(session: Session) -> dict:
    mortgage = session.scalar(select(Mortgage).order_by(Mortgage.updated_at.desc()))
    with httpx.Client(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "Financito/0.3 public-offer-research"},
    ) as client:
        sources = [_scan_source(source, client) for source in SOURCES]

    current_rate = None if mortgage is None else mortgage.nominal_rate * 100
    leads = []
    for source in sources:
        tins = [float(x["value_percent"]) for x in source["rates"] if x["type"] == "TIN"]
        min_tin = min(tins) if tins else None
        benchmark_delta = None
        if current_rate is not None and min_tin is not None:
            benchmark_delta = float(current_rate) - min_tin
        leads.append({
            "source_id": source["id"],
            "provider": source["provider"],
            "kind": source["kind"],
            "status": source["status"],
            "public_tin_min": min_tin,
            "benchmark_difference_pp": benchmark_delta,
            "promo_percent": source.get("promo_percent"),
            "claims": source["claims"],
            "url": source["url"],
            "retrieved_at": source["retrieved_at"],
            "requires_personalized_quote": True,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_mortgage_rate_percent": None if current_rate is None else str(current_rate),
        "leads": leads,
        "disclaimer": (
            "Los datos públicos son referencias de mercado y pueden no ser aplicables a una subrogación concreta. "
            "Financito no calcula ahorro neto hasta disponer de una oferta personalizada/FEIN y de los costes contractuales actuales confirmados."
        ),
    }
