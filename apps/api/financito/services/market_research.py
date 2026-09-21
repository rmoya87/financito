from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import html
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Mortgage
from ..domain.engines import MortgageEngine
from .contractual_costs import resolve_subrogation_penalty, switching_readiness


OFFICIAL_SOURCES = (
    {
        "id": "bde_mortgage_reference",
        "provider": "Banco de España",
        "kind": "official_mortgage_reference",
        "url": "https://clientebancario.bde.es/pcb/es/menu-horizontal/podemosayudarte/tiposinteres/guia_textual/tiposinteresreferenciaotrostiposfrecuentes/tabla_tipos_referencia_oficiales_mercado_hipotecario.html",
        "description": "Tipos de referencia oficiales del mercado hipotecario, incluido Euríbor e IRPH.",
    },
    {
        "id": "bde_mfi_rates",
        "provider": "Banco de España",
        "kind": "official_market_statistics",
        "url": "https://www.bde.es/webbe/es/estadisticas/temas/tipos-interes.html",
        "description": "Tipos de interés mensuales aplicados por las entidades a nuevas operaciones de vivienda.",
    },
)

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


def _market_conclusion(mortgage: Mortgage | None, leads: list[dict], readiness: dict) -> dict:
    if mortgage is None:
        return {
            "status": "needs_more_data",
            "headline": "Primero vincula una hipoteca real",
            "action": "Vincula la FEIN, escritura o condiciones vigentes a una hipoteca en Documentos antes de comparar el mercado.",
            "provider": None,
            "source_id": None,
            "missing": ["mortgage"],
            "assumptions": [],
        }

    if not readiness.get("ready"):
        return {
            "status": "needs_more_data",
            "headline": "Faltan costes contractuales para decidir",
            "action": "Confirma los datos pendientes de la documentación antes de elegir una alternativa. Financito no trata una penalización o vinculación desconocida como 0 €.",
            "provider": None,
            "source_id": None,
            "missing": readiness.get("missing", []),
            "assumptions": ["Las referencias públicas no sustituyen una FEIN/oferta personalizada."],
        }

    candidates = []
    for lead in leads:
        scenario = lead.get("scenario")
        if not scenario or lead.get("kind") not in {"mortgage_subrogation", "mortgage_public_benchmark"}:
            continue
        try:
            monthly_saving = Decimal(scenario["monthly_payment_difference"])
            interest_saving = Decimal(scenario["remaining_interest_difference"])
            penalty = Decimal(scenario["known_exit_penalty"])
            break_even = Decimal(scenario["break_even_months_known_penalty_only"])
        except (TypeError, ValueError, ArithmeticError):
            continue
        net_known = (interest_saving - penalty).quantize(Decimal("0.01"))
        if monthly_saving > 0 and net_known > 0 and break_even < Decimal(mortgage.remaining_months):
            candidates.append((net_known, monthly_saving, lead))

    if not candidates:
        return {
            "status": "keep_or_negotiate",
            "headline": "No hay una referencia pública que justifique cambiar con los datos actuales",
            "action": "Mantén la hipoteca como escenario base y usa las mejores referencias públicas solo para negociar una novación. Repite la comparación cuando exista una oferta personalizada con TAE, vinculaciones y gastos completos.",
            "provider": mortgage.lender,
            "source_id": None,
            "missing": [],
            "assumptions": ["Se compara el mismo capital pendiente y el mismo plazo restante."],
        }

    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    net_known, monthly_saving, lead = candidates[0]
    scenario = lead["scenario"]
    return {
        "status": "request_personalized_offer",
        "headline": f"La referencia más favorable para contrastar es {lead['provider']}",
        "action": (
            f"Solicita a {lead['provider']} una FEIN u oferta personalizada y pide primero a {mortgage.lender} "
            "que iguale o mejore esas condiciones. Cambia solo si la oferta final mantiene un ahorro neto positivo "
            "después de penalización, seguros vinculados, tasación y cualquier otro coste confirmado."
        ),
        "provider": lead["provider"],
        "source_id": lead["source_id"],
        "public_tin_percent": lead.get("public_tin_min"),
        "estimated_monthly_saving": str(monthly_saving),
        "estimated_remaining_interest_saving": scenario["remaining_interest_difference"],
        "known_exit_penalty": scenario["known_exit_penalty"],
        "estimated_net_interest_saving_known_costs": str(net_known),
        "break_even_months_known_penalty_only": scenario["break_even_months_known_penalty_only"],
        "missing": [],
        "assumptions": [
            "Mismo capital pendiente y plazo restante que la hipoteca seleccionada.",
            "El TIN público es una referencia y puede no ser el TIN finalmente ofrecido.",
            "El ahorro neto mostrado descuenta solo costes contractuales conocidos; la oferta final debe completar el resto.",
        ],
    }


def scan_public_market(session: Session, mortgage_id: str | None = None) -> dict:
    mortgage = session.get(Mortgage, mortgage_id) if mortgage_id else session.scalar(
        select(Mortgage).order_by(Mortgage.updated_at.desc())
    )
    with httpx.Client(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "Financito/0.3 public-offer-research"},
    ) as client:
        sources = [_scan_source(source, client) for source in SOURCES]

    current_rate = None if mortgage is None else mortgage.nominal_rate * 100
    current_scenario = None if mortgage is None else MortgageEngine.amortization(
        mortgage.remaining_principal, mortgage.nominal_rate, mortgage.remaining_months
    )
    exit_penalty = None if mortgage is None else resolve_subrogation_penalty(session, mortgage)
    leads = []
    for source in sources:
        tins = [float(x["value_percent"]) for x in source["rates"] if x["type"] == "TIN"]
        min_tin = min(tins) if tins else None
        benchmark_delta = None
        if current_rate is not None and min_tin is not None:
            benchmark_delta = float(current_rate) - min_tin
        scenario = None
        if mortgage is not None and min_tin is not None:
            candidate = MortgageEngine.amortization(
                mortgage.remaining_principal,
                Decimal(str(min_tin)) / Decimal("100"),
                mortgage.remaining_months,
            )
            monthly_delta = (
                current_scenario.monthly_payment - candidate.monthly_payment
            ).quantize(Decimal("0.01"))
            saved_payment_delta = (
                mortgage.monthly_payment - candidate.monthly_payment
            ).quantize(Decimal("0.01"))
            interest_delta = (
                current_scenario.total_interest - candidate.total_interest
            ).quantize(Decimal("0.01")) if current_scenario is not None else None
            known_penalty = None if not exit_penalty or exit_penalty["amount"] is None else exit_penalty["amount"]
            break_even = None
            if known_penalty is not None and monthly_delta > 0:
                break_even = (known_penalty / monthly_delta).quantize(Decimal("0.1"))
            scenario = {
                "estimated_payment": str(candidate.monthly_payment),
                "monthly_payment_difference": str(monthly_delta),
                "saved_payment_difference": str(saved_payment_delta),
                "remaining_interest_difference": None if interest_delta is None else str(interest_delta),
                "known_exit_penalty": None if known_penalty is None else str(known_penalty),
                "break_even_months_known_penalty_only": None if break_even is None else str(break_even),
                "comparison_scope": "same_remaining_principal_and_term",
            }
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
            "scenario": scenario,
        })

    readiness = switching_readiness(session, mortgage.id if mortgage is not None else None)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mortgage_id": None if mortgage is None else mortgage.id,
        "current_mortgage_rate_percent": None if current_rate is None else str(current_rate),
        "current_monthly_payment": None if mortgage is None else str(mortgage.monthly_payment),
        "official_sources": list(OFFICIAL_SOURCES),
        "leads": leads,
        "conclusion": _market_conclusion(mortgage, leads, readiness),
        "disclaimer": (
            "Los tipos publicados son referencias comerciales/estadísticas y no una oferta personalizada. "
            "Las simulaciones mantienen capital pendiente y plazo actuales para hacer comparable la cuota. "
            "El punto de equilibrio, cuando aparece, solo descuenta la penalización de salida confirmada; seguros vinculados, "
            "tasación, otros costes y condiciones de una FEIN deben incorporarse antes de calcular el ahorro neto."
        ),
    }
