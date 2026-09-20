from __future__ import annotations

from decimal import Decimal
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contract, Document, ExtractedFact, Mortgage
from ..models_analytics import EntityLink, LinkedProduct
from ..models_extended import InsurancePolicy
from ..domain.engines import MortgageEngine


MORTGAGE_KEYS = {
    "early_repayment_fee_percent",
    "subrogation_fee_percent",
    "cancellation_fee_percent",
    "early_exit_penalty",
    "nominal_rate",
    "apr_rate",
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


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(".", "").replace(",", ".")) if "," in str(value) else Decimal(str(value))
    except Exception:
        return None


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
        "linked_product_signals": linked,
        "source_documents": [{"id": d.id, "name": d.file_name} for d in docs],
    }


def resolve_prepayment_penalty(session: Session, mortgage: Mortgage, extra_payment: Decimal) -> dict:
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


def insurance_switching_context(session: Session) -> list[dict]:
    policies = session.scalars(select(InsurancePolicy)).all()
    out = []
    for policy in policies:
        contract = session.get(Contract, policy.contract_id) if policy.contract_id else None
        source_doc_id = None
        if contract:
            link = session.scalar(select(EntityLink).where(
                EntityLink.from_type == "document",
                EntityLink.relation_type == "evidence_for",
                EntityLink.to_type == "contract",
                EntityLink.to_id == contract.id,
            ))
            source_doc_id = link.from_id if link else None
        facts = _confirmed_facts(session, [source_doc_id] if source_doc_id else [])
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
            "confirmed_facts": facts,
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
    missing = []
    if subrogation["amount"] is None:
        missing.append("mortgage_exit_or_subrogation_penalty")
    for policy in insurance:
        if policy["evidence_status"] != "confirmed":
            missing.append(f"insurance_evidence:{policy['policy_id']}")
        if policy["cancellation_notice_days"] is None:
            missing.append(f"insurance_notice:{policy['policy_id']}")
        if policy["exit_penalty"] is None:
            missing.append(f"insurance_exit_penalty:{policy['policy_id']}")

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
        },
        "insurance": insurance,
        "hypotheses": hypotheses,
        "rule": "No se cierra una comparación si faltan costes de salida, vinculaciones o evidencia de seguro material.",
    }
