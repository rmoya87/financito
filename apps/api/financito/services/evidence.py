from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ActionItem, Contract, Document, ExtractedFact
from ..models_analytics import EntityLink
from ..models_extended import InsurancePolicy

MATERIAL_FACT_TYPES = {"contract_term", "mortgage_term", "linked_product"}
CONTRACT_DOCUMENT_TYPES = {"mortgage", "insurance", "loan", "contract", "energy", "telecom"}
REVIEWED_STATUSES = {"confirmed", "ambiguous", "conflicting", "not_found", "superseded"}


def _facts(session: Session, document_id: str) -> list[ExtractedFact]:
    return session.scalars(
        select(ExtractedFact)
        .where(
            ExtractedFact.document_id == document_id,
            ExtractedFact.fact_type.in_(MATERIAL_FACT_TYPES),
        )
        .order_by(ExtractedFact.updated_at.desc())
    ).all()


def review_summary(session: Session, document_id: str) -> dict:
    facts = _facts(session, document_id)
    pending = [f for f in facts if f.status == "inferred" and not f.user_verified]
    confirmed = [f for f in facts if f.status == "confirmed" and f.user_verified]
    ambiguous = [f for f in facts if f.status in {"ambiguous", "conflicting"}]
    reviewed = [f for f in facts if f.user_verified or f.status in REVIEWED_STATUSES]
    return {
        "total": len(facts),
        "pending": len(pending),
        "confirmed": len(confirmed),
        "ambiguous": len(ambiguous),
        "reviewed": len(reviewed),
    }


def _review_action(session: Session, document_id: str) -> ActionItem | None:
    return session.scalar(
        select(ActionItem)
        .where(
            ActionItem.action_type == "review_document_evidence",
            ActionItem.related_entity_type == "document",
            ActionItem.related_entity_id == document_id,
        )
        .order_by(ActionItem.created_at.desc())
    )


def sync_review_action(session: Session, document: Document) -> dict:
    summary = review_summary(session, document.id)
    action = _review_action(session, document.id)

    if summary["pending"] > 0:
        title = f"Revisar {summary['pending']} dato(s) extraído(s) de {document.file_name}"
        if action is None:
            action = ActionItem(
                action_type="review_document_evidence",
                title=title,
                related_entity_type="document",
                related_entity_id=document.id,
                priority="high",
                source_type="document",
                source_ref=document.id,
                notes="Revisa la evidencia extraída. Solo los datos confirmados se proyectan a contratos, seguros y cálculos deterministas.",
            )
            session.add(action)
        elif action.status == "dismissed":
            # A dismissal is an explicit user choice. Keep the evidence searchable,
            # but do not recreate the same task on every startup.
            pass
        else:
            action.title = title
            action.status = "pending"
            action.completed_at = None
    elif action is not None and action.status in {"pending", "in_progress"}:
        action.status = "done"
        action.completed_at = datetime.now().astimezone().replace(tzinfo=None)

    session.flush()
    return summary


def _payload(fact: ExtractedFact) -> dict:
    try:
        value = json.loads(fact.value_json)
        return value if isinstance(value, dict) else {"value": value}
    except Exception:
        return {"value": fact.value_json}


def _confirmed_values(session: Session, document_id: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for fact in _facts(session, document_id):
        if not (fact.user_verified and fact.status == "confirmed"):
            continue
        if fact.key not in result:
            payload = _payload(fact)
            payload["source_page"] = fact.source_page
            payload["confidence"] = str(fact.confidence)
            result[fact.key] = payload
    return result


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(Decimal(str(value).replace(",", ".")))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value: object):
    from datetime import datetime as dt

    raw = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return dt.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _label(document: Document) -> str:
    stem = Path(document.file_name).stem
    label = re.sub(r"[_\-]+", " ", stem)
    label = re.sub(r"\s+", " ", label).strip()
    return (label or "Documento")[:180]


def _insurance_type(file_name: str) -> str:
    name = file_name.lower()
    mappings = (
        (("hogar", "vivienda"), "home"),
        (("coche", "auto", "vehiculo", "vehículo"), "car"),
        (("vida",), "life"),
        (("salud", "medico", "médico"), "health"),
        (("mascota", "perro", "gato"), "pet"),
    )
    for terms, value in mappings:
        if any(term in name for term in terms):
            return value
    return "unknown"


def _entity_link(
    session: Session,
    document_id: str,
    to_type: str,
) -> EntityLink | None:
    return session.scalar(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document_id,
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == to_type,
        )
    )


def _ensure_contract_projection(
    session: Session,
    document: Document,
    values: dict[str, dict],
    summary: dict,
) -> Contract | None:
    if document.document_type not in CONTRACT_DOCUMENT_TYPES or not values:
        return None

    link = _entity_link(session, document.id, "contract")
    contract = session.get(Contract, link.to_id) if link else None
    if contract is None:
        contract = Contract(
            provider_name=_label(document),
            contract_type=document.document_type,
            currency="EUR",
            evidence_status="needs_more_data",
        )
        session.add(contract)
        session.flush()
        session.add(
            EntityLink(
                from_type="document",
                from_id=document.id,
                relation_type="evidence_for",
                to_type="contract",
                to_id=contract.id,
                confidence=Decimal("1"),
                source_type="document_projection",
                source_ref=document.id,
            )
        )

    contract.provider_name = _label(document)
    contract.contract_type = document.document_type

    if "cancellation_notice_days" in values:
        contract.cancellation_notice_days = _integer(values["cancellation_notice_days"].get("value"))
    if "early_exit_penalty" in values:
        contract.early_exit_penalty = _decimal(values["early_exit_penalty"].get("value"))
    if "annual_cost" in values:
        contract.annual_cost = _decimal(values["annual_cost"].get("value"))
    elif "monthly_cost" in values:
        monthly = _decimal(values["monthly_cost"].get("value"))
        if monthly is not None:
            contract.annual_cost = monthly * Decimal("12")
    if "renewal_date" in values:
        contract.renewal_date = _date(values["renewal_date"].get("value"))
    if "permanence_end_date" in values:
        contract.permanence_end_date = _date(values["permanence_end_date"].get("value"))

    contract.evidence_status = (
        "confirmed"
        if summary["confirmed"] > 0 and summary["pending"] == 0 and summary["ambiguous"] == 0
        else "needs_more_data"
    )
    session.flush()
    return contract


def _ensure_insurance_projection(
    session: Session,
    document: Document,
    contract: Contract | None,
    values: dict[str, dict],
) -> InsurancePolicy | None:
    if document.document_type != "insurance" or contract is None:
        return None

    premium = None
    if "annual_cost" in values:
        premium = _decimal(values["annual_cost"].get("value"))
    elif "monthly_cost" in values:
        monthly = _decimal(values["monthly_cost"].get("value"))
        premium = None if monthly is None else monthly * Decimal("12")

    link = _entity_link(session, document.id, "insurance_policy")
    policy = session.get(InsurancePolicy, link.to_id) if link else None

    # annual_premium is mandatory. Do not invent zero when the document has not
    # provided a confirmed amount.
    if policy is None and premium is None:
        return None

    if policy is None:
        policy = InsurancePolicy(
            contract_id=contract.id,
            insurance_type=_insurance_type(document.file_name),
            annual_premium=premium,
            deductible=None,
            currency="EUR",
            insured_object_json="{}",
        )
        session.add(policy)
        session.flush()
        session.add(
            EntityLink(
                from_type="document",
                from_id=document.id,
                relation_type="evidence_for",
                to_type="insurance_policy",
                to_id=policy.id,
                confidence=Decimal("1"),
                source_type="document_projection",
                source_ref=document.id,
            )
        )

    policy.contract_id = contract.id
    if premium is not None:
        policy.annual_premium = premium
    if "deductible" in values:
        policy.deductible = _decimal(values["deductible"].get("value"))
    session.flush()
    return policy


def synchronize_document_evidence(session: Session, document: Document) -> dict:
    summary = sync_review_action(session, document)
    values = _confirmed_values(session, document.id)
    contract = _ensure_contract_projection(session, document, values, summary)
    policy = _ensure_insurance_projection(session, document, contract, values)
    session.flush()
    return {
        **summary,
        "contract_id": None if contract is None else contract.id,
        "insurance_policy_id": None if policy is None else policy.id,
    }


def synchronize_all_document_evidence(session: Session) -> int:
    count = 0
    for document in session.scalars(select(Document)).all():
        synchronize_document_evidence(session, document)
        count += 1
    return count


def structured_evidence_context(
    session: Session,
    max_documents: int = 30,
    max_facts: int = 150,
) -> dict:
    documents = session.scalars(
        select(Document).order_by(Document.updated_at.desc()).limit(max_documents)
    ).all()
    out = []
    used = 0
    for document in documents:
        facts = _facts(session, document.id)
        items = []
        for fact in facts:
            if used >= max_facts:
                break
            payload = _payload(fact)
            items.append(
                {
                    "key": fact.key,
                    "value": payload.get("value"),
                    "unit": payload.get("unit"),
                    "status": fact.status,
                    "user_verified": fact.user_verified,
                    "confidence": str(fact.confidence),
                    "page": fact.source_page,
                }
            )
            used += 1
        if items:
            out.append(
                {
                    "document_id": document.id,
                    "name": document.file_name,
                    "type": document.document_type,
                    "facts": items,
                }
            )
        if used >= max_facts:
            break
    return {
        "rule": "Solo status=confirmed y user_verified=true es evidencia confirmada para cálculos deterministas. inferred/ambiguous es contexto pendiente de revisión.",
        "documents": out,
    }
