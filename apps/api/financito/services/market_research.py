from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import html
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract,Mortgage
from ..models_analytics import LinkedProduct
from ..models_extended import CoverageFact,InsurancePolicy
from ..domain.engines import MortgageEngine
from .contractual_costs import insurance_switching_context,resolve_subrogation_penalty,switching_readiness


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

INSURANCE_KIND_TO_TYPE = {
    "home_insurance": "home",
    "mortgage_life_insurance": "life",
    "life_insurance": "life",
}


def _plain_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _rates(text: str) -> list[dict]:
    found = []
    patterns = {
        "TIN": (
            r"(\d{1,2}(?:[\.,]\d{1,3})?)\s*%\s*TIN",
            r"TIN[^\d%]{0,35}(\d{1,2}(?:[\.,]\d{1,3})?)\s*%",
        ),
        "TAE": (
            r"(\d{1,2}(?:[\.,]\d{1,3})?)\s*%\s*TAE(?:\s+Variable)?",
            r"TAE(?:\s+Variable)?[^\d%]{0,35}(\d{1,2}(?:[\.,]\d{1,3})?)\s*%",
        ),
    }
    for label, candidates in patterns.items():
        seen = set()
        for pattern in candidates:
            for match in re.finditer(pattern, text, re.I):
                value = match.group(1).replace(",", ".")
                if value in seen:
                    continue
                seen.add(value)
                found.append({"type": label, "value_percent": value})
                if len(seen) >= 5:
                    break
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
        ("linked_card", r"(?:contratar|usar|utilizaci[oó]n|gasto).{0,60}tarjeta|tarjeta.{0,60}(?:contratar|usar|utilizaci[oó]n|gasto)"),
        ("linked_pension_plan", r"plan de pensiones|plan de previsi[oó]n"),
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


def _insurance_market_leads(session:Session,sources:list[dict])->list[dict]:
    current=insurance_switching_context(session)
    coverage_counts={
        policy_id:len(session.scalars(select(CoverageFact).where(
            CoverageFact.insurance_policy_id==policy_id,
            CoverageFact.user_verified.is_(True),
        )).all())
        for policy_id in [row["policy_id"] for row in current]
    }
    leads=[]
    for source in sources:
        insurance_type=INSURANCE_KIND_TO_TYPE.get(source["kind"])
        if not insurance_type:
            continue
        current_rows=[]
        for policy in current:
            normalized=str(policy.get("insurance_type") or "").lower()
            equivalent_type=normalized in (
                {"home","house","hogar","mortgage","hipoteca"}
                if insurance_type=="home"
                else {"life","vida"}
            )
            if not equivalent_type:
                continue
            current_rows.append({
                "policy_id":policy["policy_id"],
                "insurance_type":policy["insurance_type"],
                "provider":policy.get("provider"),
                "annual_premium":policy["annual_premium"],
                "deductible":policy.get("deductible"),
                "renewal_date":policy.get("renewal_date"),
                "cancellation_notice_days":policy.get("cancellation_notice_days"),
                "exit_penalty":policy.get("exit_penalty"),
                "evidence_status":policy.get("evidence_status"),
                "verified_coverage_count":coverage_counts.get(policy["policy_id"],0),
                "linked_mortgage_ids":policy.get("linked_mortgage_ids",[]),
            })
        leads.append({
            "source_id":source["id"],
            "provider":source["provider"],
            "kind":source["kind"],
            "insurance_type":insurance_type,
            "status":source["status"],
            "url":source["url"],
            "retrieved_at":source["retrieved_at"],
            "claims":source["claims"],
            "current_policies":current_rows,
            "comparison_status":"needs_personalized_quote",
            "can_decide":False,
            "missing_candidate_data":[
                "candidate_annual_premium",
                "candidate_deductible",
                "equivalent_verified_coverages_and_limits",
                "candidate_exclusions",
                "candidate_cancellation_terms",
                "candidate_entry_or_switching_costs",
            ],
            "rule":(
                "La página pública sirve para descubrir una alternativa, no para declarar que es mejor. "
                "Hace falta una oferta personalizada y demostrar equivalencia de cobertura."
            ),
        })
    return leads


def _linked_mortgage_conditions(session:Session,mortgage:Mortgage|None)->dict:
    if mortgage is None:
        return {
            "policies":[],
            "annual_premium_total":"0",
            "known_exit_penalty_total":"0",
            "unknown_exit_penalty_policy_ids":[],
            "rate_impacts":[],
            "linked_product_signals":[],
        }
    links=session.scalars(select(LinkedProduct).where(
        LinkedProduct.parent_product_type=="mortgage",
        LinkedProduct.parent_product_id==mortgage.id,
        LinkedProduct.linked_product_type=="insurance_policy",
    )).all()
    policies=[];annual=Decimal("0")
    for link in links:
        policy=session.get(InsurancePolicy,link.linked_product_id)
        if policy is None:
            continue
        contract=session.get(Contract,policy.contract_id) if policy.contract_id else None
        annual+=policy.annual_premium
        policies.append({
            "policy_id":policy.id,
            "insurance_type":policy.insurance_type,
            "annual_premium":str(policy.annual_premium),
            "provider":None if contract is None else contract.provider_name,
            "exit_penalty":None if contract is None or contract.early_exit_penalty is None else str(contract.early_exit_penalty),
            "conditions":link.conditions,
        })
    readiness=switching_readiness(session,mortgage.id)
    known_exit_penalty_total=sum(
        (Decimal(row["exit_penalty"]) for row in policies if row["exit_penalty"] is not None),
        Decimal("0"),
    )
    unknown_exit_penalty_policy_ids=[
        row["policy_id"] for row in policies if row["exit_penalty"] is None
    ]
    return {
        "policies":policies,
        "annual_premium_total":str(annual.quantize(Decimal("0.01"))),
        "known_exit_penalty_total":str(known_exit_penalty_total.quantize(Decimal("0.01"))),
        "unknown_exit_penalty_policy_ids":unknown_exit_penalty_policy_ids,
        "rate_impacts":((readiness.get("mortgage") or {}).get("linked_product_rate_impacts") or []),
        "linked_product_signals":((readiness.get("mortgage") or {}).get("linked_product_signals") or []),
    }


def _market_conclusion(
    mortgage: Mortgage | None,
    better_offers: list[dict],
    rejected_or_readiness: list[dict] | dict | None = None,
    readiness: dict | None = None,
) -> dict:
    # Backwards-compatible direct-call shape used by existing callers/tests:
    # _market_conclusion(mortgage, leads, readiness).
    compatibility_mode = readiness is None and isinstance(rejected_or_readiness, dict)
    if compatibility_mode:
        readiness = rejected_or_readiness
        raw_leads = better_offers
        better_offers = []
        rejected = []
        if mortgage is not None and readiness.get("ready"):
            for lead in raw_leads:
                scenario = lead.get("scenario") or {}
                try:
                    monthly_saving = Decimal(str(
                        scenario.get("actual_monthly_saving")
                        or scenario.get("monthly_payment_difference")
                    ))
                    interest_saving = Decimal(str(scenario["remaining_interest_difference"]))
                    penalty = Decimal(str(scenario["known_exit_penalty"]))
                    break_even = Decimal(str(
                        scenario.get("break_even_months")
                        or scenario.get("break_even_months_known_penalty_only")
                    ))
                except (KeyError,TypeError,ValueError,ArithmeticError):
                    continue
                net_known=(interest_saving-penalty).quantize(Decimal("0.01"))
                if monthly_saving>0 and net_known>0 and break_even<Decimal(mortgage.remaining_months):
                    normalized={**lead,"scenario":{
                        **scenario,
                        "actual_monthly_saving":str(monthly_saving),
                        "estimated_net_interest_saving_known_costs":str(net_known),
                        "break_even_months":str(break_even),
                        "compensates":True,
                    }}
                    better_offers.append(normalized)
        elif mortgage is not None:
            return {
                "status":"needs_more_data",
                "headline":"Faltan costes contractuales para decidir",
                "action":"Confirma los datos pendientes antes de valorar un cambio. Financito no trata costes desconocidos como 0 €.",
                "provider":None,
                "source_id":None,
                "missing":readiness.get("missing",[]),
                "assumptions":["Las referencias públicas no sustituyen una FEIN/oferta personalizada."],
            }
    else:
        rejected = rejected_or_readiness if isinstance(rejected_or_readiness,list) else []
        readiness = readiness or {"ready":True,"missing":[]}

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

    if better_offers:
        lead=sorted(
            better_offers,
            key=lambda item: Decimal((item.get("scenario") or {}).get("estimated_net_interest_saving_known_costs") or "0"),
            reverse=True,
        )[0]
        scenario=lead["scenario"]
        return {
            "status":"request_personalized_offer",
            "headline":f"{len(better_offers)} referencia(s) pública(s) justifican pedir una oferta personalizada",
            "action":(
                f"La referencia con mayor mejora estimada es {lead['provider']}. Solicita una FEIN/oferta personalizada "
                f"y compárala con tu hipoteca actual. No se considera una hipoteca mejor hasta incorporar todos los costes "
                f"y vinculaciones de la oferta final. Con los datos públicos actuales, el punto de equilibrio estimado sería "
                f"de unos {scenario['break_even_months']} meses."
            ),
            "provider":lead["provider"],
            "source_id":lead["source_id"],
            "public_tin_percent":lead.get("public_tin_min"),
            "estimated_monthly_saving":scenario["actual_monthly_saving"],
            "estimated_remaining_interest_saving":scenario["remaining_interest_difference"],
            "known_exit_penalty":scenario["known_exit_penalty"],
            "estimated_net_interest_saving_known_costs":scenario["estimated_net_interest_saving_known_costs"],
            "break_even_months":scenario["break_even_months"],
            # Compatibility alias for clients created before the stricter market filter.
            "break_even_months_known_penalty_only":scenario["break_even_months"],
            "missing":[],
            "assumptions":[
                "Se usa el mismo capital pendiente y plazo restante.",
                "El ahorro mensual se compara contra tu cuota guardada actual.",
                "Solo se muestran como mejores las referencias cuyo ahorro conocido supera la penalización y cuyo punto de equilibrio llega antes del final de la hipoteca.",
                "Una referencia con cualquier vinculación o coste de entrada no confirmado no se considera mejor hasta conocerlo.",
            ],
        }

    lower_rate_count=sum(1 for row in rejected if row.get("rate_better"))
    missing=readiness.get("missing",[])
    if lower_rate_count:
        headline="Hay tipos públicos más bajos, pero no se ha demostrado que te compense cambiar"
        action=(
            "No se muestra ninguna como mejor oferta porque, al aplicar tu cuota, plazo y penalización, "
            "o bien el punto de equilibrio no llega antes del fin de la hipoteca o faltan costes de vinculaciones de la nueva oferta."
        )
    else:
        headline="No hay una referencia pública que mejore tu hipoteca con los datos actuales"
        action="Mantén estas referencias como apoyo para negociar y vuelve a comparar cuando cambien las ofertas o tus condiciones."
    return {
        "status":"keep_or_negotiate" if not missing else "needs_more_data",
        "headline":headline,
        "action":action,
        "provider":mortgage.lender,
        "source_id":None,
        "missing":missing,
        "assumptions":["Las referencias públicas no sustituyen una FEIN/oferta personalizada."],
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
    linked_conditions=_linked_mortgage_conditions(session,mortgage)
    leads=[];better_offers=[];rejected=[]
    for source in sources:
        tins=[float(x["value_percent"]) for x in source["rates"] if x["type"]=="TIN"]
        taes=[float(x["value_percent"]) for x in source["rates"] if x["type"]=="TAE"]
        min_tin=min(tins) if tins else None
        min_tae=min(taes) if taes else None
        benchmark_delta=None if current_rate is None or min_tin is None else float(current_rate)-min_tin
        scenario=None
        rate_better=bool(current_rate is not None and min_tin is not None and Decimal(str(min_tin))<current_rate)
        if mortgage is not None and min_tin is not None:
            candidate=MortgageEngine.amortization(
                mortgage.remaining_principal,
                Decimal(str(min_tin))/Decimal("100"),
                mortgage.remaining_months,
            )
            theoretical_saving=(current_scenario.monthly_payment-candidate.monthly_payment).quantize(Decimal("0.01"))
            actual_saving=(mortgage.monthly_payment-candidate.monthly_payment).quantize(Decimal("0.01"))
            interest_delta=(current_scenario.total_interest-candidate.total_interest).quantize(Decimal("0.01"))
            known_penalty=None if not exit_penalty or exit_penalty["amount"] is None else exit_penalty["amount"]
            break_even=None
            if known_penalty is not None and actual_saving>0:
                break_even=(known_penalty/actual_saving).quantize(Decimal("0.1"))
            priced_link_unknown=any(
                claim in source["claims"] for claim in (
                    "linked_home_insurance","linked_life_insurance","salary_link","linked_card","linked_pension_plan"
                )
            )
            unpriced_entry_costs=[] if "no_opening_fee" in source["claims"] else ["opening_or_arrangement_cost"]
            comparison_complete=(
                known_penalty is not None
                and not priced_link_unknown
                and not unpriced_entry_costs
            )
            net_known=None if known_penalty is None else (interest_delta-known_penalty).quantize(Decimal("0.01"))
            compensates=bool(
                source["kind"] in {"mortgage_subrogation","mortgage_public_benchmark"}
                and rate_better
                and actual_saving>0
                and net_known is not None and net_known>0
                and break_even is not None and break_even<Decimal(mortgage.remaining_months)
                and comparison_complete
            )
            reason=None
            if not rate_better:
                reason="El TIN publicado no mejora tu TIN actual."
            elif known_penalty is None:
                reason="Falta confirmar la penalización/coste de salida de tu hipoteca."
            elif actual_saving<=0:
                reason="La cuota comparable no mejora tu cuota actual guardada."
            elif break_even is None or break_even>=Decimal(mortgage.remaining_months):
                reason="La penalización no se recupera antes de terminar el plazo restante."
            elif net_known is not None and net_known<=0:
                reason="El ahorro de intereses conocido no supera la penalización de salida."
            elif priced_link_unknown:
                if any(claim in source["claims"] for claim in ("linked_home_insurance","linked_life_insurance")):
                    reason="La oferta exige seguro vinculado y hace falta una oferta personalizada para valorar su coste y cobertura."
                else:
                    reason="La oferta pública incluye una vinculación que debe valorarse con una oferta personalizada antes de afirmar que compensa."
            elif unpriced_entry_costs:
                reason="Faltan costes de entrada de la nueva hipoteca; no se presuponen 0 € aunque el TIN sea inferior."
            scenario={
                "estimated_payment":str(candidate.monthly_payment),
                "theoretical_monthly_saving":str(theoretical_saving),
                "actual_monthly_saving":str(actual_saving),
                "monthly_payment_difference":str(actual_saving),
                "remaining_interest_difference":str(interest_delta),
                "known_exit_penalty":None if known_penalty is None else str(known_penalty),
                "estimated_net_interest_saving_known_costs":None if net_known is None else str(net_known),
                "break_even_months":None if break_even is None else str(break_even),
                "break_even_months_known_penalty_only":None if break_even is None else str(break_even),
                "compensates":compensates,
                "comparison_complete":comparison_complete,
                "unpriced_entry_costs":unpriced_entry_costs,
                "rejection_reason":reason,
                "comparison_scope":"same_remaining_principal_and_term_vs_saved_current_payment",
            }
        lead={
            "source_id":source["id"],
            "provider":source["provider"],
            "kind":source["kind"],
            "status":source["status"],
            "public_tin_min":min_tin,
            "public_tae_min":min_tae,
            "benchmark_difference_pp":benchmark_delta,
            "promo_percent":source.get("promo_percent"),
            "claims":source["claims"],
            "url":source["url"],
            "retrieved_at":source["retrieved_at"],
            "requires_personalized_quote":True,
            "rate_better":rate_better,
            "scenario":scenario,
        }
        leads.append(lead)
        if scenario and scenario["compensates"]:
            better_offers.append(lead)
        elif source["kind"] in {"mortgage_subrogation","mortgage_public_benchmark"} and rate_better:
            rejected.append(lead)

    readiness=switching_readiness(session,mortgage.id if mortgage is not None else None)
    insurance_leads=_insurance_market_leads(session,sources)
    better_offers.sort(
        key=lambda item:Decimal((item.get("scenario") or {}).get("estimated_net_interest_saving_known_costs") or "0"),
        reverse=True,
    )
    return {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "mortgage_id":None if mortgage is None else mortgage.id,
        "current_mortgage_rate_percent":None if current_rate is None else str(current_rate),
        "current_monthly_payment":None if mortgage is None else str(mortgage.monthly_payment),
        "current_conditions":{
            "remaining_months":None if mortgage is None else mortgage.remaining_months,
            "known_exit_penalty":None if not exit_penalty or exit_penalty["amount"] is None else str(exit_penalty["amount"]),
            "exit_penalty_status":None if not exit_penalty else exit_penalty["status"],
            "linked_insurance_annual_cost":linked_conditions["annual_premium_total"],
            "linked_insurance_known_exit_penalty_total":linked_conditions["known_exit_penalty_total"],
            "linked_insurance_unknown_exit_penalty_policy_ids":linked_conditions["unknown_exit_penalty_policy_ids"],
            "linked_policies":linked_conditions["policies"],
            "linked_product_rate_impacts":linked_conditions["rate_impacts"],
            "linked_product_signals":linked_conditions["linked_product_signals"],
        },
        "official_sources":list(OFFICIAL_SOURCES),
        "leads":leads,
        "insurance_leads":insurance_leads,
        "insurance_market_summary":{
            "references":len(insurance_leads),
            "decision_ready":0,
            "message":(
                "Las referencias públicas de seguros sirven para localizar proveedores. "
                "Financito no declara ninguna mejor sin prima personalizada y cobertura equivalente verificada."
            ),
        },
        "better_offers":better_offers,
        "lower_rate_but_not_better":rejected,
        "conclusion":_market_conclusion(mortgage,better_offers,rejected,readiness),
        "disclaimer":(
            "Solo se muestran como mejores las referencias que, con la cuota, capital, plazo y penalización confirmada actuales, "
            "mantienen ahorro conocido positivo y recuperan el coste de salida antes del fin de la hipoteca. "
            "Si la nueva referencia exige vinculaciones cuyo coste/condición no está confirmado o no confirma los costes de entrada, "
            "no se afirma que sea mejor aunque su TIN sea inferior. Los costes de cancelar seguros actuales solo se aplican "
            "cuando se compara un cambio de paquete completo, no al escenario de cambiar únicamente la hipoteca. "
            "Una FEIN/oferta personalizada sigue siendo necesaria para cerrar la decisión."
        ),
    }
