from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.engines import MortgagePrepaymentEngine
from ..models import Mortgage
from .contractual_costs import insurance_switching_context, resolve_prepayment_penalty
from .decision_context import live_decision_context


def _insurance_choice_rows(session: Session, context: dict) -> list[dict]:
    policy_details = {
        row["id"]: row
        for row in (context.get("insurance") or {}).get("policies", [])
    }
    mortgages = {row["id"]: row for row in context.get("mortgages", [])}
    rows = []
    for policy in insurance_switching_context(session):
        detail = policy_details.get(policy["policy_id"], {})
        verified_coverages = [
            coverage
            for coverage in detail.get("coverages", [])
            if coverage.get("user_verified")
        ]
        missing = []
        if policy.get("evidence_status") != "confirmed":
            missing.append("confirmed_policy_evidence")
        if policy.get("cancellation_notice_days") is None:
            missing.append("cancellation_notice_days")
        if policy.get("exit_penalty") is None:
            missing.append("exit_penalty")
        if not verified_coverages:
            missing.append("verified_coverages")

        mortgage_impacts = []
        normalized_type = str(policy.get("insurance_type") or "").lower()
        impact_product = (
            "home_insurance"
            if normalized_type in {"home", "house", "hogar", "mortgage", "hipoteca"}
            else "life_insurance"
            if normalized_type in {"life", "vida"}
            else None
        )
        for mortgage_id in policy.get("linked_mortgage_ids", []):
            mortgage = mortgages.get(mortgage_id)
            if mortgage is None:
                continue
            impacts = ((mortgage.get("switching_readiness") or {}).get("mortgage") or {}).get(
                "linked_product_rate_impacts", []
            )
            for impact in impacts:
                if impact_product and impact.get("product") == impact_product:
                    mortgage_impacts.append({
                        "mortgage_id": mortgage_id,
                        "lender": mortgage.get("lender"),
                        **impact,
                    })

        notice_deadline = None
        if policy.get("renewal_date") and policy.get("cancellation_notice_days") is not None:
            try:
                renewal = date.fromisoformat(policy["renewal_date"])
                notice_deadline = str(
                    renewal - timedelta(days=int(policy["cancellation_notice_days"]))
                )
            except Exception:
                notice_deadline = None

        rows.append({
            **policy,
            "verified_coverage_count": len(verified_coverages),
            "verified_coverages": verified_coverages,
            "mortgage_rate_impacts_if_removed": mortgage_impacts,
            "notice_deadline": notice_deadline,
            "status": "ready_for_personalized_quote" if not missing else "needs_more_data",
            "missing": missing,
            "comparison_requirements": [
                "candidate_annual_premium",
                "candidate_deductible",
                "equivalent_verified_coverages_and_limits",
                "candidate_exclusions",
                "candidate_cancellation_terms",
                "candidate_entry_or_switching_costs",
                "mortgage_bonus_loss_if_linked",
            ],
            "rule": (
                "Una alternativa no puede considerarse favorable por precio si no demuestra "
                "cobertura equivalente y el impacto de perder vinculaciones hipotecarias."
            ),
        })
    return rows


def _prepayment_guardrail(session: Session, context: dict, mortgage: Mortgage | None) -> dict:
    liquidity = Decimal(str(context.get("liquidity") or "0"))
    average_expenses = Decimal(
        str((context.get("cash_flow_last_90_days") or {}).get("average_monthly_expenses") or "0")
    )
    reference_months = 6
    if average_expenses <= 0:
        return {
            "status": "needs_more_data",
            "protected_liquidity_reference_months": reference_months,
            "protected_liquidity_reference": None,
            "cash_above_reference": None,
            "illustrative_extra_payment": None,
            "scenario": None,
            "missing": ["expense_history"],
            "notice": (
                "No se calcula capacidad ilustrativa de amortización sin histórico de gasto. "
                "El colchón de seis meses es una referencia de planificación, no una recomendación."
            ),
        }

    protected = (average_expenses * Decimal(reference_months)).quantize(Decimal("0.01"))
    available = max(Decimal("0"), liquidity - protected).quantize(Decimal("0.01"))
    if mortgage is None:
        return {
            "status": "needs_mortgage",
            "protected_liquidity_reference_months": reference_months,
            "protected_liquidity_reference": str(protected),
            "cash_above_reference": str(available),
            "illustrative_extra_payment": None,
            "scenario": None,
            "missing": ["mortgage"],
            "notice": (
                "El colchón de seis meses es una referencia de planificación, no una recomendación de liquidez."
            ),
        }

    extra = min(available, mortgage.remaining_principal).quantize(Decimal("0.01"))
    if extra <= 0:
        return {
            "status": "no_cash_above_reference",
            "protected_liquidity_reference_months": reference_months,
            "protected_liquidity_reference": str(protected),
            "cash_above_reference": "0.00",
            "illustrative_extra_payment": "0.00",
            "scenario": None,
            "missing": [],
            "notice": (
                "Con esta referencia de colchón no queda efectivo excedente para una simulación. "
                "No se interpreta como una recomendación de mantener exactamente seis meses."
            ),
        }

    penalty = resolve_prepayment_penalty(session, mortgage, extra)
    if penalty.get("amount") is None:
        return {
            "status": "needs_more_data",
            "protected_liquidity_reference_months": reference_months,
            "protected_liquidity_reference": str(protected),
            "cash_above_reference": str(available),
            "illustrative_extra_payment": str(extra),
            "scenario": None,
            "missing": ["prepayment_penalty"],
            "penalty": penalty,
            "notice": (
                "No se calcula el ahorro neto de amortizar hasta confirmar la comisión aplicable. "
                "La cantidad simulada es solo el efectivo por encima del colchón de referencia."
            ),
        }

    scenario = MortgagePrepaymentEngine.compare(
        mortgage.remaining_principal,
        mortgage.nominal_rate,
        mortgage.remaining_months,
        extra,
        Decimal(str(penalty["amount"])),
    )
    return {
        "status": "illustrative",
        "protected_liquidity_reference_months": reference_months,
        "protected_liquidity_reference": str(protected),
        "cash_above_reference": str(available),
        "illustrative_extra_payment": str(extra),
        "penalty": {
            **penalty,
            "amount": str(penalty["amount"]),
        },
        "scenario": {
            "original_monthly_payment": str(scenario.original_monthly_payment),
            "reduced_payment": str(scenario.reduced_payment),
            "reduced_term_months": scenario.reduced_term_months,
            "interest_saved_reduce_payment": str(scenario.interest_saved_reduce_payment),
            "interest_saved_reduce_term": str(scenario.interest_saved_reduce_term),
        },
        "missing": [],
        "notice": (
            "Escenario ilustrativo: usa como máximo el efectivo situado por encima de seis meses "
            "del gasto medio reciente. No indica cuánto debe amortizar el usuario."
        ),
    }


def decision_overview(session: Session, mortgage_id: str | None = None) -> dict:
    context = live_decision_context(session)
    mortgage_record = None
    mortgage_summary = None
    if mortgage_id:
        mortgage_record = session.get(Mortgage, mortgage_id)
        if mortgage_record is None:
            raise ValueError("Mortgage not found")
        mortgage_summary = next(
            (row for row in context.get("mortgages", []) if row["id"] == mortgage_id),
            None,
        )
    else:
        mortgage_record = session.scalar(select(Mortgage).order_by(Mortgage.updated_at.desc()))
        if mortgage_record is not None:
            mortgage_summary = next(
                (row for row in context.get("mortgages", []) if row["id"] == mortgage_record.id),
                None,
            )

    insurance_rows = _insurance_choice_rows(session, context)
    prepayment = _prepayment_guardrail(session, context, mortgage_record)
    cards = []

    if mortgage_summary is None:
        cards.append({
            "id": "mortgage-switch",
            "domain": "mortgage",
            "title": "Cambiar o renegociar hipoteca",
            "status": "needs_more_data",
            "headline": "Falta una hipoteca vinculada para comparar alternativas.",
            "missing": ["mortgage"],
            "next_action": "Añade o vincula la hipoteca y su documentación contractual.",
            "path": "/wealth/#casa",
        })
    else:
        readiness = mortgage_summary.get("switching_readiness") or {}
        missing = readiness.get("missing") or []
        cards.append({
            "id": "mortgage-switch",
            "domain": "mortgage",
            "title": "Cambiar o renegociar hipoteca",
            "status": "ready_for_market_check" if readiness.get("ready") else "needs_more_data",
            "headline": (
                "Tus costes de salida y vinculaciones actuales están preparados para contrastar una oferta."
                if readiness.get("ready")
                else "Antes de comparar falta confirmar alguna condición contractual material."
            ),
            "missing": missing,
            "next_action": (
                "Compara referencias y solicita una FEIN/oferta personalizada antes de cerrar la decisión."
                if readiness.get("ready")
                else "Confirma los datos pendientes en la documentación de la hipoteca o seguros vinculados."
            ),
            "path": "/wealth/#casa",
        })

    prepayment_missing = prepayment.get("missing") or []
    cards.append({
        "id": "mortgage-prepayment",
        "domain": "mortgage",
        "title": "Amortizar hipoteca",
        "status": prepayment["status"],
        "headline": (
            "Hay un escenario ilustrativo calculable sin consumir el colchón de liquidez de referencia."
            if prepayment["status"] == "illustrative"
            else "La simulación de amortización necesita más datos o liquidez por encima del colchón de referencia."
        ),
        "missing": prepayment_missing,
        "next_action": (
            "Abre la simulación y cambia el importe o el colchón según tu situación."
            if prepayment["status"] == "illustrative"
            else "Revisa el dato pendiente antes de usar el resultado para decidir."
        ),
        "path": "/tools/",
    })

    for policy in insurance_rows:
        provider = policy.get("provider") or policy.get("insurance_type") or "Seguro"
        cards.append({
            "id": "insurance-switch:" + policy["policy_id"],
            "domain": "insurance",
            "title": f"Revisar seguro · {provider}",
            "status": policy["status"],
            "headline": (
                "La póliza actual ya tiene datos suficientes para pedir una alternativa equivalente."
                if policy["status"] == "ready_for_personalized_quote"
                else "Faltan condiciones de la póliza actual antes de poder comparar de forma segura."
            ),
            "missing": policy["missing"],
            "next_action": (
                "Pide una oferta personalizada y compara prima, franquicia, coberturas, exclusiones y vinculaciones."
                if policy["status"] == "ready_for_personalized_quote"
                else "Completa o confirma la evidencia pendiente de la póliza."
            ),
            "path": "/insurance/?policy=" + policy["policy_id"],
        })

    requiring_data = sum(1 for card in cards if card["status"] in {"needs_more_data", "needs_mortgage"})
    return {
        "generated_at": context["generated_at"],
        "summary": {
            "choices": len(cards),
            "requiring_data": requiring_data,
            "alerts": len(context.get("decision_alerts", [])),
            "pending_actions": len(context.get("actions", [])),
        },
        "financial_context": {
            "liquidity": context["liquidity"],
            "cash_flow_current_month": context["cash_flow_current_month"],
            "cash_flow_last_90_days": context["cash_flow_last_90_days"],
            "wealth": context["wealth"],
        },
        "mortgage": mortgage_summary,
        "prepayment_guardrail": prepayment,
        "insurance": insurance_rows,
        "signals": context.get("decision_alerts", []),
        "pending_actions": context.get("actions", []),
        "choice_cards": cards,
        "rules": [
            "No se decide por TIN, TAE o prima aislados.",
            "Costes de salida, entrada, vinculaciones y beneficios perdidos se muestran por separado.",
            "Un coste o penalización material desconocido bloquea una conclusión favorable.",
            "En seguros se exige equivalencia de coberturas, límites y exclusiones antes de comparar ahorro.",
            "El colchón de seis meses usado en la simulación de amortización es una referencia de planificación, no una recomendación.",
            "La IA local puede explicar estos resultados, pero no sustituye los motores deterministas.",
        ],
    }
