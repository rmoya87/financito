from __future__ import annotations

from decimal import Decimal
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract, Document, ExtractedFact, Mortgage
from ..models_analytics import EntityLink, LinkedProduct
from ..models_extended import InsurancePolicy,MortgageProfileExtra
from ..domain.engines import MortgageEngine


PREPAYMENT_RULE_KEYS = {
    "partial_prepayment_allowed",
    "prepayment_min_amount",
    "prepayment_max_amount",
    "prepayment_min_percent_current_balance",
    "prepayment_max_percent_current_balance",
    "prepayment_notice_days",
    "prepayment_frequency_limit_per_year",
    "prepayment_window",
    "prepayment_condition",
    "prepayment_reduction_options",
}

MORTGAGE_KEYS = {
    "early_repayment_fee_percent",
    "subrogation_fee_percent",
    "cancellation_fee_percent",
    "early_exit_penalty",
    "nominal_rate",
    "apr_rate",
    "reference_index",
    "differential_rate",
    "reference_index_lag_months",
    "rate_review_months",
    "next_review_date",
    "opening_fee_percent",
    "remaining_principal",
    "monthly_payment",
    "linked_salary",
    "linked_home_insurance",
    "linked_life_insurance",
    "linked_card",
    "linked_pension_plan",
    "linked_home_insurance_rate_penalty_pp",
    "linked_life_insurance_rate_penalty_pp",
    "linked_salary_rate_penalty_pp",
    *PREPAYMENT_RULE_KEYS,
}


def _payload(row: ExtractedFact) -> dict:
    try:
        raw = json.loads(row.value_json)
        return raw if isinstance(raw, dict) else {"value": raw}
    except Exception:
        return {"value": row.value_json}


def _confirmed_facts(session: Session, document_ids: list[str], keys: set[str] | None = None) -> list[dict]:
    if not document_ids:
        return []
    stmt = select(ExtractedFact).where(
        ExtractedFact.document_id.in_(document_ids),
        ExtractedFact.status == "confirmed",
        ExtractedFact.user_verified.is_(True),
    )
    if keys:
        stmt = stmt.where(ExtractedFact.key.in_(keys))
    rows = session.scalars(stmt.order_by(ExtractedFact.updated_at.desc())).all()
    out = []
    seen = set()
    for row in rows:
        if row.key in seen:
            continue
        seen.add(row.key)
        payload = _payload(row)
        out.append(
            {
                "key": row.key,
                "value": payload.get("value"),
                "unit": payload.get("unit"),
                "document_id": row.document_id,
                "page": row.source_page,
                "confidence": str(row.confidence),
            }
        )
    return out


def _pending_facts(session: Session, document_ids: list[str], keys: set[str] | None = None) -> list[dict]:
    if not document_ids:
        return []
    stmt = select(ExtractedFact).where(
        ExtractedFact.document_id.in_(document_ids),
        ExtractedFact.user_verified.is_(False),
        ExtractedFact.status.in_(["inferred", "ambiguous", "conflicting"]),
    )
    if keys:
        stmt = stmt.where(ExtractedFact.key.in_(keys))
    rows = session.scalars(stmt.order_by(ExtractedFact.updated_at.desc())).all()
    out = []
    seen = set()
    for row in rows:
        if row.key in seen:
            continue
        seen.add(row.key)
        payload = _payload(row)
        out.append(
            {
                "key": row.key,
                "value": payload.get("value"),
                "unit": payload.get("unit"),
                "document_id": row.document_id,
                "page": row.source_page,
                "confidence": str(row.confidence),
                "status": row.status,
                "source": payload.get("source") or "deterministic_extractor",
            }
        )
    return out


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(".", "").replace(",", ".")) if "," in str(value) else Decimal(str(value))
    except Exception:
        return None


def _as_bool(value) -> bool | None:
    if value is None:
        return None
    normalized=str(value).strip().lower()
    if normalized in {"true","1","yes","sí","si","allowed","permitido","permitida","autorizado","autorizada"}:
        return True
    if normalized in {"false","0","no","not_allowed","prohibido","prohibida","no permitido","no permitida"}:
        return False
    return None


def _reduction_options(value) -> list[str]:
    if value is None:
        return []
    normalized=str(value).strip().lower().replace("-","_").replace(" ","_")
    if normalized in {"both","ambos","ambas","cuota_y_plazo","payment_and_term","term_and_payment"}:
        return ["payment","term"]
    if normalized in {"payment","cuota","reduce_payment","reducir_cuota"}:
        return ["payment"]
    if normalized in {"term","plazo","reduce_term","reducir_plazo"}:
        return ["term"]
    if normalized in {"lender_choice","eleccion_entidad","elección_entidad","bank_choice"}:
        return ["lender_choice"]
    return []


def prepayment_restrictions(
    session: Session,
    mortgage: Mortgage,
    extra_payment: Decimal | None = None,
) -> dict:
    """Resolve confirmed contractual limits for a partial early repayment.

    The function never treats an unknown permission/limit as zero or as
    permission. Confirmed restrictions are enforceable; inferred restrictions
    block execution until the user validates or rejects them in the source
    document.
    """
    ctx=mortgage_contract_context(session,mortgage.id)
    by_key=ctx["by_key"]
    pending_by_key=ctx["pending_by_key"]
    pending=[
        pending_by_key[key]
        for key in PREPAYMENT_RULE_KEYS
        if key in pending_by_key
    ]

    permission_fact=by_key.get("partial_prepayment_allowed")
    permission=_as_bool(None if permission_fact is None else permission_fact.get("value"))
    reduction_fact=by_key.get("prepayment_reduction_options")
    reduction_options=_reduction_options(None if reduction_fact is None else reduction_fact.get("value"))

    min_amount=_as_decimal((by_key.get("prepayment_min_amount") or {}).get("value"))
    max_amount=_as_decimal((by_key.get("prepayment_max_amount") or {}).get("value"))
    min_pct=_as_decimal((by_key.get("prepayment_min_percent_current_balance") or {}).get("value"))
    max_pct=_as_decimal((by_key.get("prepayment_max_percent_current_balance") or {}).get("value"))
    min_candidates=[value for value in (
        min_amount,
        None if min_pct is None else mortgage.remaining_principal*min_pct/Decimal("100"),
    ) if value is not None]
    max_candidates=[value for value in (
        max_amount,
        None if max_pct is None else mortgage.remaining_principal*max_pct/Decimal("100"),
        mortgage.remaining_principal,
    ) if value is not None]
    effective_min=max(min_candidates).quantize(Decimal("0.01")) if min_candidates else None
    effective_max=min(max_candidates).quantize(Decimal("0.01")) if max_candidates else mortgage.remaining_principal.quantize(Decimal("0.01"))

    notice=_as_decimal((by_key.get("prepayment_notice_days") or {}).get("value"))
    frequency=_as_decimal((by_key.get("prepayment_frequency_limit_per_year") or {}).get("value"))
    window=(by_key.get("prepayment_window") or {}).get("value")
    condition=(by_key.get("prepayment_condition") or {}).get("value")

    missing=[]
    blockers=[]
    if pending:
        blockers.append({
            "code":"pending_contract_terms",
            "message":"Hay condiciones de amortización encontradas en la documentación pendientes de confirmar.",
            "keys":[row["key"] for row in pending],
        })
    if permission is None:
        missing.append("partial_prepayment_allowed")
    elif permission is False:
        blockers.append({
            "code":"partial_prepayment_not_allowed",
            "message":"La evidencia contractual confirmada no permite esta amortización parcial.",
        })
    if permission is True and not reduction_options:
        missing.append("prepayment_reduction_options")

    amount=None if extra_payment is None else Decimal(str(extra_payment))
    if amount is not None:
        if amount<=0:
            blockers.append({"code":"invalid_amount","message":"El importe a amortizar debe ser mayor que 0."})
        if amount>mortgage.remaining_principal:
            blockers.append({
                "code":"exceeds_remaining_principal",
                "message":"El importe supera el capital pendiente de la hipoteca.",
                "limit":str(mortgage.remaining_principal.quantize(Decimal("0.01"))),
            })
        if effective_min is not None and amount<effective_min:
            blockers.append({
                "code":"below_contract_minimum",
                "message":"El importe está por debajo del mínimo contractual confirmado.",
                "limit":str(effective_min),
            })
        if effective_max is not None and amount>effective_max:
            blockers.append({
                "code":"above_contract_maximum",
                "message":"El importe supera el máximo contractual confirmado.",
                "limit":str(effective_max),
            })

    operational_checks=[]
    if notice is None:
        operational_checks.append({
            "code":"notice_not_confirmed",
            "message":"No está confirmado si debes avisar al banco con antelación.",
        })
    elif notice>0:
        operational_checks.append({
            "code":"notice_required",
            "message":f"El contrato exige un preaviso de {int(notice)} días.",
            "confirmed":True,
        })
    if frequency is not None and frequency>0:
        operational_checks.append({
            "code":"frequency_limit",
            "message":f"El contrato limita la amortización a {int(frequency)} vez/veces por año; Financito no dispone aún de un contador contractual de usos.",
            "confirmed":True,
        })
    if window not in {None,""}:
        operational_checks.append({
            "code":"contract_window",
            "message":f"Ventana contractual confirmada: {window}.",
            "confirmed":True,
        })
    if condition not in {None,""}:
        operational_checks.append({
            "code":"contract_condition",
            "message":f"Condición contractual confirmada: {condition}.",
            "confirmed":True,
        })
    if reduction_options==["lender_choice"]:
        operational_checks.append({
            "code":"lender_chooses_reduction",
            "message":"La entidad decide cómo se aplica la amortización; no se puede asumir reducción de cuota o plazo.",
            "confirmed":True,
        })

    hard_block=any(row["code"] not in {"notice_required","frequency_limit","contract_window","contract_condition"} for row in blockers)
    calculation_ready=permission is True and not missing and not pending and not hard_block
    requires_manual_execution_check=any(
        row["code"] in {"notice_not_confirmed","frequency_limit","contract_window","contract_condition","lender_chooses_reduction"}
        for row in operational_checks
    )
    status=(
        "not_allowed" if permission is False
        else "needs_review" if pending
        else "needs_more_data" if missing
        else "amount_not_allowed" if blockers
        else "ready_with_manual_check" if requires_manual_execution_check
        else "ready"
    )
    return {
        "status":status,
        "calculation_ready":calculation_ready,
        "permission_confirmed":permission is not None,
        "partial_prepayment_allowed":permission,
        "missing":sorted(set(missing)),
        "pending_review":pending,
        "blockers":blockers,
        "effective_min_amount":None if effective_min is None else str(effective_min),
        "effective_max_amount":None if effective_max is None else str(effective_max),
        "notice_days":None if notice is None else int(notice),
        "frequency_limit_per_year":None if frequency is None else int(frequency),
        "window":None if window in {None,""} else str(window),
        "condition":None if condition in {None,""} else str(condition),
        "allowed_reduction_options":reduction_options,
        "operational_checks":operational_checks,
        "requires_manual_execution_check":requires_manual_execution_check,
        "sources":{
            key:by_key[key] for key in PREPAYMENT_RULE_KEYS if key in by_key
        },
        "rule":"Los límites y permisos desconocidos no se convierten en 0 ni en permiso implícito; los indicios pendientes deben confirmarse antes de decidir.",
    }


def mortgage_contract_context(session: Session, mortgage_id: str | None = None) -> dict:
    mortgage = session.get(Mortgage, mortgage_id) if mortgage_id else session.scalar(
        select(Mortgage).order_by(Mortgage.updated_at.desc())
    )
    linked_doc_ids=[]
    if mortgage is not None:
        linked_doc_ids=list(session.scalars(select(EntityLink.from_id).where(
            EntityLink.from_type=="document",
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="mortgage",
            EntityLink.to_id==mortgage.id,
        )).all())
    docs=session.scalars(select(Document).where(Document.id.in_(linked_doc_ids)).order_by(Document.updated_at.desc())).all() if linked_doc_ids else []
    doc_ids = [d.id for d in docs]
    facts = _confirmed_facts(session, doc_ids, MORTGAGE_KEYS)
    by_key = {x["key"]: x for x in facts}
    pending_facts = _pending_facts(session, doc_ids, MORTGAGE_KEYS)
    pending_by_key = {x["key"]: x for x in pending_facts}
    linked = [x for x in facts if x["key"].startswith("linked_")]

    return {
        "mortgage": None if mortgage is None else {
            "id": mortgage.id,
            "lender": mortgage.lender,
            "remaining_principal": str(mortgage.remaining_principal),
            "nominal_rate": str(mortgage.nominal_rate),
            "monthly_payment": str(mortgage.monthly_payment),
            "remaining_months": mortgage.remaining_months,
            "early_repayment_fee": None if mortgage.early_repayment_fee is None else str(mortgage.early_repayment_fee),
        },
        "facts": facts,
        "by_key": by_key,
        "pending_facts": pending_facts,
        "pending_by_key": pending_by_key,
        "linked_product_signals": linked,
        "source_documents": [{"id": d.id, "name": d.file_name} for d in docs],
    }


def _mortgage_extra(session: Session, mortgage_id: str) -> MortgageProfileExtra | None:
    return session.scalar(
        select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id == mortgage_id)
    )


def resolve_prepayment_penalty(session: Session, mortgage: Mortgage, extra_payment: Decimal) -> dict:
    extra = _mortgage_extra(session, mortgage.id)
    if extra is not None and extra.early_repayment_fee_percent is not None:
        pct = extra.early_repayment_fee_percent
        amount = (extra_payment * pct / Decimal("100")).quantize(Decimal("0.01"))
        return {
            "status": "user_profile_formula",
            "amount": amount,
            "formula": f"{pct}% × {extra_payment}",
            "source": {"type":"mortgage_profile_extra","field":"early_repayment_fee_percent"},
        }
    ctx = mortgage_contract_context(session, mortgage.id)
    by_key = ctx["by_key"]
    pct = _as_decimal((by_key.get("early_repayment_fee_percent") or {}).get("value"))
    if pct is not None:
        amount = (extra_payment * pct / Decimal("100")).quantize(Decimal("0.01"))
        return {
            "status": "confirmed_formula",
            "amount": amount,
            "formula": f"{pct}% × {extra_payment}",
            "source": by_key["early_repayment_fee_percent"],
        }
    if mortgage.early_repayment_fee is not None:
        return {
            "status": "confirmed_value",
            "amount": mortgage.early_repayment_fee,
            "formula": "importe guardado",
            "source": None,
        }
    return {"status": "needs_more_data", "amount": None, "formula": None, "source": None}


def resolve_subrogation_penalty(session: Session, mortgage: Mortgage) -> dict:
    extra = _mortgage_extra(session, mortgage.id)
    if extra is not None:
        for key in ("subrogation_fee_percent", "cancellation_fee_percent", "early_repayment_fee_percent"):
            pct = getattr(extra,key)
            if pct is not None:
                amount = (mortgage.remaining_principal * pct / Decimal("100")).quantize(Decimal("0.01"))
                return {
                    "status": "user_profile_formula",
                    "amount": amount,
                    "formula": f"{pct}% × {mortgage.remaining_principal}",
                    "source": {"type":"mortgage_profile_extra","field":key},
                    "fact_key": key,
                }
    ctx = mortgage_contract_context(session, mortgage.id)
    by_key = ctx["by_key"]
    for key in ("subrogation_fee_percent", "cancellation_fee_percent", "early_repayment_fee_percent"):
        pct = _as_decimal((by_key.get(key) or {}).get("value"))
        if pct is not None:
            amount = (mortgage.remaining_principal * pct / Decimal("100")).quantize(Decimal("0.01"))
            return {
                "status": "confirmed_formula",
                "amount": amount,
                "formula": f"{pct}% × {mortgage.remaining_principal}",
                "source": by_key[key],
                "fact_key": key,
            }
    if mortgage.early_repayment_fee is not None:
        return {
            "status": "confirmed_value",
            "amount": mortgage.early_repayment_fee,
            "formula": "importe guardado",
            "source": None,
            "fact_key": "early_repayment_fee",
        }
    return {"status": "needs_more_data", "amount": None, "formula": None, "source": None, "fact_key": None}


def linked_product_rate_impacts(session: Session, mortgage: Mortgage) -> list[dict]:
    ctx = mortgage_contract_context(session, mortgage.id)
    by_key = ctx["by_key"]
    base = MortgageEngine.amortization(mortgage.remaining_principal, mortgage.nominal_rate, mortgage.remaining_months)
    mappings = (
        ("home_insurance", "linked_home_insurance_rate_penalty_pp"),
        ("life_insurance", "linked_life_insurance_rate_penalty_pp"),
        ("salary", "linked_salary_rate_penalty_pp"),
    )
    out = []
    for product, key in mappings:
        fact = by_key.get(key)
        pp = _as_decimal(None if fact is None else fact.get("value"))
        if pp is None:
            continue
        delta_rate = pp / Decimal("100")
        alt = MortgageEngine.amortization(
            mortgage.remaining_principal,
            mortgage.nominal_rate + delta_rate,
            mortgage.remaining_months,
        )
        out.append({
            "product": product,
            "fact_key": key,
            "rate_penalty_pp": str(pp),
            "monthly_payment_at_current_rate": str(base.monthly_payment),
            "monthly_payment_without_product": str(alt.monthly_payment),
            "monthly_payment_increase": str((alt.monthly_payment-base.monthly_payment).quantize(Decimal("0.01"))),
            "remaining_interest_increase": str((alt.total_interest-base.total_interest).quantize(Decimal("0.01"))),
            "source": fact,
            "assumption": (
                "fixed_rate_contract"
                if mortgage.interest_type == "fixed"
                else "current_rate_held_constant_for_comparison"
            ),
        })
    return out


def insurance_switching_context(session: Session, mortgage_id: str | None = None) -> list[dict]:
    policies = session.scalars(select(InsurancePolicy)).all()
    out = []
    for policy in policies:
        linked_mortgage_ids=list(session.scalars(select(LinkedProduct.parent_product_id).where(
            LinkedProduct.parent_product_type=="mortgage",
            LinkedProduct.linked_product_type=="insurance_policy",
            LinkedProduct.linked_product_id==policy.id,
        )).all())
        contract = session.get(Contract, policy.contract_id) if policy.contract_id else None
        source_doc_ids = []
        if contract:
            source_doc_ids = list(session.scalars(select(EntityLink.from_id).where(
                EntityLink.from_type == "document",
                EntityLink.relation_type == "evidence_for",
                EntityLink.to_type == "contract",
                EntityLink.to_id == contract.id,
            )).all())
        facts = _confirmed_facts(session, source_doc_ids)
        source_doc_id = source_doc_ids[0] if source_doc_ids else None
        out.append({
            "policy_id": policy.id,
            "insurance_type": policy.insurance_type,
            "annual_premium": str(policy.annual_premium),
            "deductible": None if policy.deductible is None else str(policy.deductible),
            "contract_id": None if contract is None else contract.id,
            "provider": None if contract is None else contract.provider_name,
            "renewal_date": None if contract is None or contract.renewal_date is None else str(contract.renewal_date),
            "cancellation_notice_days": None if contract is None else contract.cancellation_notice_days,
            "exit_penalty": None if contract is None or contract.early_exit_penalty is None else str(contract.early_exit_penalty),
            "evidence_status": None if contract is None else contract.evidence_status,
            "source_document_id": source_doc_id,
            "source_document_ids": source_doc_ids,
            "document_count": len(source_doc_ids),
            "confirmed_facts": facts,
            "linked_mortgage_ids": linked_mortgage_ids,
            "linked_to_mortgage": mortgage_id in linked_mortgage_ids if mortgage_id else False,
        })
    return out


def switching_readiness(session: Session, mortgage_id: str | None = None) -> dict:
    mortgage = session.get(Mortgage, mortgage_id) if mortgage_id else session.scalar(
        select(Mortgage).order_by(Mortgage.updated_at.desc())
    )
    insurance = insurance_switching_context(session)
    if mortgage is None:
        return {
            "ready": False,
            "missing": ["mortgage"],
            "mortgage": None,
            "insurance": insurance,
            "hypotheses": [],
        }

    subrogation = resolve_subrogation_penalty(session, mortgage)
    mctx = mortgage_contract_context(session, mortgage.id)
    linked_signals = [x["key"] for x in mctx["linked_product_signals"]]
    insurance = insurance_switching_context(session,mortgage.id)
    linked_insurance=[policy for policy in insurance if policy["linked_to_mortgage"]]
    missing = []
    if subrogation["amount"] is None:
        missing.append("mortgage_exit_or_subrogation_penalty")
    for policy in linked_insurance:
        if policy["evidence_status"] != "confirmed":
            missing.append(f"insurance_evidence:{policy['policy_id']}")
        if policy["cancellation_notice_days"] is None:
            missing.append(f"insurance_notice:{policy['policy_id']}")
        if policy["exit_penalty"] is None:
            missing.append(f"insurance_exit_penalty:{policy['policy_id']}")
    normalized_types={str(policy["insurance_type"] or "").lower() for policy in linked_insurance}
    if "linked_home_insurance" in linked_signals and not any(x in normalized_types for x in {"home","house","hogar","mortgage","hipoteca"}):
        missing.append("linked_insurance_mapping:home")
    if "linked_life_insurance" in linked_signals and not any(x in normalized_types for x in {"life","vida"}):
        missing.append("linked_insurance_mapping:life")

    hypotheses = [
        {"key": "keep_all", "label": "Mantener hipoteca y seguros actuales"},
        {"key": "renegotiate_mortgage", "label": "Renegociar/novar la hipoteca actual y mantener seguros"},
        {"key": "switch_mortgage_keep_insurance", "label": "Cambiar solo la hipoteca y mantener seguros si la nueva entidad lo permite"},
        {"key": "switch_insurance_keep_mortgage", "label": "Mantener hipoteca y cambiar seguros por separado"},
        {"key": "switch_mortgage_and_insurance", "label": "Cambiar hipoteca y seguros a la nueva entidad"},
        {"key": "switch_mortgage_external_insurance", "label": "Cambiar hipoteca y contratar seguros fuera del banco"},
        {"key": "prepay_keep", "label": "Amortizar parcialmente y mantener hipoteca/seguros"},
        {"key": "prepay_then_switch", "label": "Amortizar parcialmente y después cambiar hipoteca"},
    ]
    return {
        "ready": len(missing) == 0,
        "missing": sorted(set(missing)),
        "mortgage": {
            "id": mortgage.id,
            "lender": mortgage.lender,
            "remaining_principal": str(mortgage.remaining_principal),
            "nominal_rate": str(mortgage.nominal_rate),
            "monthly_payment": str(mortgage.monthly_payment),
            "remaining_months": mortgage.remaining_months,
            "subrogation_penalty": {
                **subrogation,
                "amount": None if subrogation["amount"] is None else str(subrogation["amount"]),
            },
            "linked_product_signals": linked_signals,
            "linked_product_rate_impacts": linked_product_rate_impacts(session, mortgage),
            "prepayment_restrictions": prepayment_restrictions(session, mortgage),
        },
        "insurance": insurance,
        "hypotheses": hypotheses,
        "rule": "No se cierra una comparación si faltan costes de salida, vinculaciones o evidencia de seguro material.",
    }
