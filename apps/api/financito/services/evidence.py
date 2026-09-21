from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re

from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..models import ActionItem, Contract, Document, ExtractedFact, Mortgage
from ..models_analytics import EntityLink,LinkedProduct
from ..models_extended import CoverageFact,InsurancePolicy,MortgageProfileExtra
from .document_ai import latest_analysis

MATERIAL_FACT_TYPES = {"contract_term", "mortgage_term", "linked_product", "coverage_fact", "investment_term"}
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
    pending = [
        f for f in facts
        if not f.user_verified and f.status in {"inferred", "ambiguous", "conflicting"}
    ]
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


IDENTITY_KEYS = {"policy_number", "contract_number", "provider_name", "insurance_type", "insured_object"}


def _normalize_identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _identity_values(session: Session, document_id: str) -> dict[str, str]:
    """Identity hints may be inferred, but are only used to suggest/auto-link
    when the identifier is strong enough; they never become confirmed facts.
    """
    result: dict[str, str] = {}
    rows = session.scalars(
        select(ExtractedFact)
        .where(
            ExtractedFact.document_id == document_id,
            ExtractedFact.key.in_(IDENTITY_KEYS),
        )
        .order_by(ExtractedFact.user_verified.desc(), ExtractedFact.confidence.desc())
    ).all()
    for fact in rows:
        if fact.key in result:
            continue
        if not fact.user_verified and fact.confidence < Decimal("0.78"):
            continue
        value = _payload(fact).get("value")
        normalized = _normalize_identity(value)
        if normalized:
            result[fact.key] = normalized
    return result


def _fact_has_insurance_context(session: Session, fact: ExtractedFact) -> bool:
    """Return True when a generic identifier sits in an insurance section.

    This prevents an insurance contract number embedded in a mortgage PDF from
    becoming a mortgage identity key for sibling-document grouping.
    """
    rows = _facts(session, fact.document_id)
    for candidate in rows:
        same_page = (
            fact.source_page is None
            or candidate.source_page is None
            or candidate.source_page == fact.source_page
        )
        if not same_page:
            continue
        if candidate.fact_type == "coverage_fact":
            return True
        if candidate.key in {
            "insurance_type",
            "insured_object",
            "policy_number",
            "linked_insurance",
            "linked_life_insurance",
            "linked_home_insurance",
            "linked_mortgage_insurance",
        }:
            return True
        if candidate.fact_type == "linked_product" and "insurance" in candidate.key.lower():
            return True
    return False


def _linked_document_ids(session: Session, to_type: str, to_id: str) -> list[str]:
    return list(session.scalars(
        select(EntityLink.from_id).where(
            EntityLink.from_type == "document",
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == to_type,
            EntityLink.to_id == to_id,
        )
    ).all())


def _add_evidence_link(
    session: Session,
    document_id: str,
    to_type: str,
    to_id: str,
    *,
    confidence: Decimal = Decimal("1"),
    source_type: str = "user",
) -> EntityLink:
    existing = session.scalar(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document_id,
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == to_type,
            EntityLink.to_id == to_id,
        )
    )
    if existing:
        return existing
    row = EntityLink(
        from_type="document",
        from_id=document_id,
        relation_type="evidence_for",
        to_type=to_type,
        to_id=to_id,
        confidence=confidence,
        source_type=source_type,
        source_ref=document_id,
    )
    session.add(row)
    session.flush()
    return row


def auto_link_document_entity(session: Session, document: Document) -> dict | None:
    """Group documents by strong product identifiers without confirming facts.

    Policy/contract numbers are identity hints, not confirmed financial facts.
    They may correct a coarse initial classifier (for example, a mediator note
    classified as contract that carries the same policy number as an insurance
    policy). Provider/type alone is never enough to merge products.
    """
    policy_link = _entity_link(session, document.id, "insurance_policy")
    if policy_link is not None:
        return {"entity_type": "insurance_policy", "entity_id": policy_link.to_id, "matched_by": "existing_link"}
    mortgage_link = _entity_link(session, document.id, "mortgage")
    if mortgage_link is not None:
        return {"entity_type": "mortgage", "entity_id": mortgage_link.to_id, "matched_by": "existing_link"}

    identities = _identity_values(session, document.id)
    policy_number = identities.get("policy_number")
    contract_number = identities.get("contract_number")

    if policy_number:
        other_facts = session.scalars(
            select(ExtractedFact).where(
                ExtractedFact.document_id != document.id,
                ExtractedFact.key == "policy_number",
            )
        ).all()
        for fact in other_facts:
            if _normalize_identity(_payload(fact).get("value")) != policy_number:
                continue

            linked_policy = _entity_link(session, fact.document_id, "insurance_policy")
            if linked_policy is not None:
                document.document_type = "insurance"
                _add_evidence_link(
                    session, document.id, "insurance_policy", linked_policy.to_id,
                    confidence=Decimal("0.98"), source_type="document_identity",
                )
                policy = session.get(InsurancePolicy, linked_policy.to_id)
                if policy and policy.contract_id:
                    _add_evidence_link(
                        session, document.id, "contract", policy.contract_id,
                        confidence=Decimal("0.98"), source_type="document_identity",
                    )
                return {
                    "entity_type": "insurance_policy",
                    "entity_id": linked_policy.to_id,
                    "matched_by": "policy_number",
                }

            linked_contract = _entity_link(session, fact.document_id, "contract")
            contract = session.get(Contract, linked_contract.to_id) if linked_contract else None
            if contract is not None and contract.contract_type == "insurance":
                document.document_type = "insurance"
                _add_evidence_link(
                    session, document.id, "contract", contract.id,
                    confidence=Decimal("0.96"), source_type="document_identity",
                )
                return {
                    "entity_type": "contract",
                    "entity_id": contract.id,
                    "matched_by": "policy_number",
                }

        # A strong policy number is enough to keep documents together before a
        # confirmed premium exists, but it never invents the premium or terms.
        current_contract = _entity_link(session, document.id, "contract")
        if current_contract is not None:
            contract = session.get(Contract, current_contract.to_id)
            if contract is not None and contract.contract_type == "insurance":
                document.document_type = "insurance"
                return {"entity_type": "contract", "entity_id": contract.id, "matched_by": "existing_link"}

        contract = Contract(
            provider_name=_label(document),
            contract_type="insurance",
            currency="EUR",
            evidence_status="needs_more_data",
        )
        session.add(contract)
        session.flush()
        document.document_type = "insurance"
        _add_evidence_link(
            session, document.id, "contract", contract.id,
            confidence=Decimal("0.90"), source_type="document_identity_group",
        )
        return {"entity_type": "contract", "entity_id": contract.id, "matched_by": "policy_number"}

    if contract_number:
        other_facts = session.scalars(
            select(ExtractedFact).where(
                ExtractedFact.document_id != document.id,
                ExtractedFact.key == "contract_number",
            )
        ).all()
        for fact in other_facts:
            if _normalize_identity(_payload(fact).get("value")) != contract_number:
                continue

            if _fact_has_insurance_context(session, fact):
                linked_policy = _entity_link(session, fact.document_id, "insurance_policy")
                if linked_policy is not None:
                    document.document_type = "insurance"
                    _add_evidence_link(
                        session, document.id, "insurance_policy", linked_policy.to_id,
                        confidence=Decimal("0.98"), source_type="document_identity",
                    )
                    policy = session.get(InsurancePolicy, linked_policy.to_id)
                    if policy is not None and policy.contract_id:
                        _add_evidence_link(
                            session, document.id, "contract", policy.contract_id,
                            confidence=Decimal("0.98"), source_type="document_identity",
                        )
                    return {
                        "entity_type": "insurance_policy",
                        "entity_id": linked_policy.to_id,
                        "matched_by": "contract_number_insurance_context",
                    }

                insurance_contract = _insurance_contract_for_document(session, fact.document_id)
                if insurance_contract is not None:
                    document.document_type = "insurance"
                    _add_evidence_link(
                        session, document.id, "contract", insurance_contract.id,
                        confidence=Decimal("0.96"), source_type="document_identity",
                    )
                    return {
                        "entity_type": "contract",
                        "entity_id": insurance_contract.id,
                        "matched_by": "contract_number_insurance_context",
                    }
                # The identifier is visibly part of an insurance section. Do
                # not fall through and reuse the mortgage link of the container
                # document as the identity target.
                continue

            linked_mortgage = _entity_link(session, fact.document_id, "mortgage")
            if linked_mortgage is not None:
                document.document_type = "mortgage"
                _add_evidence_link(
                    session, document.id, "mortgage", linked_mortgage.to_id,
                    confidence=Decimal("0.98"), source_type="document_identity",
                )
                return {
                    "entity_type": "mortgage",
                    "entity_id": linked_mortgage.to_id,
                    "matched_by": "contract_number",
                }

            linked_contract = _entity_link(session, fact.document_id, "contract")
            if linked_contract is None:
                continue
            contract = session.get(Contract, linked_contract.to_id)
            if contract is None:
                continue
            if contract.contract_type == "insurance":
                document.document_type = "insurance"
                policy = session.scalar(
                    select(InsurancePolicy).where(InsurancePolicy.contract_id == contract.id)
                )
                if policy is not None:
                    _add_evidence_link(
                        session, document.id, "insurance_policy", policy.id,
                        confidence=Decimal("0.96"), source_type="document_identity",
                    )
            elif contract.contract_type != "mortgage":
                document.document_type = contract.contract_type
            _add_evidence_link(
                session, document.id, "contract", contract.id,
                confidence=Decimal("0.98"), source_type="document_identity",
            )
            return {
                "entity_type": "contract",
                "entity_id": contract.id,
                "matched_by": "contract_number",
            }

        current_contract = _entity_link(session, document.id, "contract")
        if current_contract is not None:
            return {
                "entity_type": "contract",
                "entity_id": current_contract.to_id,
                "matched_by": "existing_link",
            }

        if document.document_type in {"contract", "loan", "energy", "telecom", "insurance"}:
            contract = Contract(
                provider_name=_label(document),
                contract_type=document.document_type,
                currency="EUR",
                evidence_status="needs_more_data",
            )
            session.add(contract)
            session.flush()
            _add_evidence_link(
                session, document.id, "contract", contract.id,
                confidence=Decimal("0.90"), source_type="document_identity_group",
            )
            return {
                "entity_type": "contract",
                "entity_id": contract.id,
                "matched_by": "contract_number",
            }

    contract_link = _entity_link(session, document.id, "contract")
    if contract_link is not None:
        return {"entity_type": "contract", "entity_id": contract_link.to_id, "matched_by": "existing_link"}
    return None


def create_document_evidence_group(session: Session, document: Document) -> dict:
    """Create an explicit grouping shell without inventing financial facts."""
    if document.document_type not in {"insurance", "contract", "loan", "energy", "telecom"}:
        raise ValueError("Este tipo de documento no admite una ficha contractual provisional")
    existing = _entity_link(session, document.id, "contract")
    if existing is not None:
        return {"entity_type": "contract", "entity_id": existing.to_id}

    contract = Contract(
        provider_name=_label(document),
        contract_type=document.document_type,
        currency="EUR",
        evidence_status="needs_more_data",
    )
    session.add(contract)
    session.flush()
    _add_evidence_link(
        session, document.id, "contract", contract.id,
        confidence=Decimal("1"), source_type="user_group",
    )
    session.flush()
    synchronize_document_evidence(session, document)
    return {"entity_type": "contract", "entity_id": contract.id}


def _cleanup_orphan_projection(
    session: Session, entity_type: str, entity_id: str, source_type: str
) -> None:
    if source_type != "document_projection":
        return
    still_linked = session.scalar(
        select(EntityLink.id).where(
            EntityLink.from_type == "document",
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == entity_type,
            EntityLink.to_id == entity_id,
        )
    )
    if still_linked:
        return
    if entity_type == "insurance_policy":
        if session.scalar(select(CoverageFact.id).where(CoverageFact.insurance_policy_id == entity_id)):
            return
        policy = session.get(InsurancePolicy, entity_id)
        if policy is not None:
            session.delete(policy)
    elif entity_type == "contract":
        if session.scalar(select(InsurancePolicy.id).where(InsurancePolicy.contract_id == entity_id)):
            return
        if session.scalar(select(CoverageFact.id).where(CoverageFact.contract_id == entity_id)):
            return
        contract = session.get(Contract, entity_id)
        if contract is not None:
            session.delete(contract)
    session.flush()


def link_document_to_entity(
    session: Session, document: Document, entity_type: str, entity_id: str | None
) -> dict:
    if entity_type not in {"insurance_policy", "contract", "mortgage"}:
        raise ValueError("Unsupported evidence entity type")

    old_links = session.scalars(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document.id,
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == entity_type,
        )
    ).all()
    orphan_candidates = [(link.to_type, link.to_id, link.source_type) for link in old_links]
    for link in old_links:
        session.delete(link)

    # Insurance documents also carry a supporting contract link. When the user
    # moves/unlinks a document, remove that old document->contract relation too;
    # a new policy contract is attached below when appropriate.
    target_contract = (
        session.get(Contract, entity_id)
        if entity_type == "contract" and entity_id
        else None
    )
    if entity_type == "insurance_policy":
        contract_links = session.scalars(
            select(EntityLink).where(
                EntityLink.from_type == "document",
                EntityLink.from_id == document.id,
                EntityLink.relation_type == "evidence_for",
                EntityLink.to_type == "contract",
            )
        ).all()
        orphan_candidates.extend(
            (link.to_type, link.to_id, link.source_type) for link in contract_links
        )
        for link in contract_links:
            session.delete(link)
    elif target_contract is not None and target_contract.contract_type == "insurance":
        policy_links = session.scalars(
            select(EntityLink).where(
                EntityLink.from_type == "document",
                EntityLink.from_id == document.id,
                EntityLink.relation_type == "evidence_for",
                EntityLink.to_type == "insurance_policy",
            )
        ).all()
        orphan_candidates.extend(
            (link.to_type, link.to_id, link.source_type) for link in policy_links
        )
        for link in policy_links:
            session.delete(link)
    session.flush()

    if entity_id:
        if entity_type == "insurance_policy":
            target = session.get(InsurancePolicy, entity_id)
            if target is None:
                raise ValueError("Insurance policy not found")
            document.document_type = "insurance"
            _add_evidence_link(session, document.id, entity_type, entity_id)
            if target.contract_id:
                _add_evidence_link(session, document.id, "contract", target.contract_id)
        elif entity_type == "contract":
            target = session.get(Contract, entity_id)
            if target is None:
                raise ValueError("Contract not found")
            if target.contract_type == "insurance":
                document.document_type = "insurance"
            elif target.contract_type == "mortgage":
                document.document_type = "mortgage"
            else:
                document.document_type = target.contract_type
            _add_evidence_link(session, document.id, entity_type, entity_id)
        else:
            target = session.get(Mortgage, entity_id)
            if target is None:
                raise ValueError("Mortgage not found")
            document.document_type = "mortgage"
            _add_evidence_link(session, document.id, entity_type, entity_id)

    session.flush()
    result = synchronize_document_evidence(session, document)
    session.flush()
    for old_type, old_id, source_type in orphan_candidates:
        if old_id != entity_id:
            _cleanup_orphan_projection(session, old_type, old_id, source_type)
    return result


def _confirm_coherent_for_documents(session: Session, document_ids: list[str]) -> dict:
    if not document_ids:
        return {"documents": 0, "confirmed": 0, "conflicts": 0}
    rows = session.scalars(
        select(ExtractedFact).where(
            ExtractedFact.document_id.in_(document_ids),
            ExtractedFact.fact_type.in_(MATERIAL_FACT_TYPES),
        )
    ).all()
    by_key: dict[str, list[ExtractedFact]] = {}
    coverage: list[ExtractedFact] = []
    for row in rows:
        if row.fact_type == "coverage_fact":
            if not row.user_verified and row.status in {"inferred", "ambiguous", "conflicting"}:
                coverage.append(row)
        else:
            by_key.setdefault(row.key, []).append(row)

    confirmed = 0
    conflicts = 0
    for items in by_key.values():
        unresolved = [
            item for item in items
            if not item.user_verified and item.status in {"inferred", "ambiguous", "conflicting"}
        ]
        if not unresolved:
            continue
        reference_values = {
            _normalize_identity(_payload(item).get("value"))
            for item in items
            if item.status not in {"not_found", "superseded"}
        }
        reference_values.discard("")
        if len(reference_values) <= 1:
            for item in unresolved:
                item.status = "confirmed"
                item.user_verified = True
                confirmed += 1
        else:
            for item in unresolved:
                item.status = "conflicting"
                item.user_verified = False
                conflicts += 1
    for item in coverage:
        item.status = "confirmed"
        item.user_verified = True
        confirmed += 1

    for document_id in document_ids:
        document = session.get(Document, document_id)
        if document:
            synchronize_document_evidence(session, document)
    session.flush()
    return {"documents": len(document_ids), "confirmed": confirmed, "conflicts": conflicts}


def confirm_document_coherent_evidence(session: Session, document_id: str) -> dict:
    return _confirm_coherent_for_documents(session, [document_id])


def confirm_entity_coherent_evidence(session: Session, entity_type: str, entity_id: str) -> dict:
    if entity_type not in {"insurance_policy", "contract", "mortgage"}:
        raise ValueError("Unsupported evidence entity type")
    return _confirm_coherent_for_documents(session, _linked_document_ids(session, entity_type, entity_id))


MORTGAGE_VALUE_KEYS = {
    "provider_name",
    "remaining_principal",
    "nominal_rate",
    "monthly_payment",
    "remaining_months",
    "interest_type",
    "mortgage_term_years",
    "apr_rate",
    "reference_index",
    "differential_rate",
    "rate_review_months",
    "next_review_date",
    "opening_fee_percent",
    "early_repayment_fee",
    "early_repayment_fee_percent",
    "subrogation_fee_percent",
    "cancellation_fee_percent",
}
INSURANCE_MARKER_KEYS = {
    "insurance_type",
    "insured_object",
    "policy_number",
    "linked_insurance",
    "linked_life_insurance",
    "linked_home_insurance",
    "linked_mortgage_insurance",
}
INSURANCE_VALUE_KEYS = {
    "provider_name",
    "annual_cost",
    "monthly_cost",
    "renewal_date",
    "next_review_date",
    "cancellation_notice_days",
    "early_exit_penalty",
    "start_date",
    "permanence_end_date",
    "insurance_type",
    "insured_object",
    "policy_number",
    "contract_number",
    "deductible",
}


def _confirmed_fact_rows(session: Session, document_id: str) -> list[dict]:
    rows = []
    for fact in _facts(session, document_id):
        if not (fact.user_verified and fact.status == "confirmed"):
            continue
        payload = _payload(fact)
        rows.append({
            "key": fact.key,
            "fact_type": fact.fact_type,
            "source_page": fact.source_page,
            "confidence": str(fact.confidence),
            "payload": payload,
        })
    return rows


def _rows_to_values(rows: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        if row["key"] in result:
            continue
        payload = dict(row["payload"])
        payload["source_page"] = row["source_page"]
        payload["confidence"] = row["confidence"]
        payload["_fact_type"] = row["fact_type"]
        result[row["key"]] = payload
    return result


def _confirmed_values(session: Session, document_id: str) -> dict[str, dict]:
    return _rows_to_values(_confirmed_fact_rows(session, document_id))


def _partition_confirmed_values(
    document: Document,
    rows: list[dict],
) -> tuple[dict[str, dict], dict[str, dict], bool]:
    """Separate confirmed facts by product domain before projecting them.

    A mortgage PDF may include a linked life/home policy. Generic contract keys
    such as provider_name, annual_cost or renewal_date must therefore not be
    allowed to overwrite mortgage fields merely because they live in the same
    file. Confirmed fact_type + the pages carrying explicit insurance markers
    provide the boundary.
    """
    all_values = _rows_to_values(rows)
    if document.document_type == "insurance":
        return {}, all_values, bool(all_values)

    insurance_marker_pages = {
        row["source_page"]
        for row in rows
        if (
            row["fact_type"] == "coverage_fact"
            or row["key"] in INSURANCE_MARKER_KEYS
            or (row["fact_type"] == "linked_product" and "insurance" in row["key"].lower())
        )
        and row["source_page"] is not None
    }
    has_insurance = any(
        row["fact_type"] == "coverage_fact"
        or row["key"] in INSURANCE_MARKER_KEYS
        or (row["fact_type"] == "linked_product" and "insurance" in row["key"].lower())
        for row in rows
    )

    mortgage_rows: list[dict] = []
    insurance_rows: list[dict] = []
    for row in rows:
        key = row["key"]
        fact_type = row["fact_type"]
        page = row["source_page"]

        # A fact explicitly classified as mortgage data wins even if the same
        # page also contains a bundled insurance product.
        if fact_type == "mortgage_term":
            mortgage_rows.append(row)
        elif key in MORTGAGE_VALUE_KEYS and page not in insurance_marker_pages:
            mortgage_rows.append(row)

        if not has_insurance:
            continue
        if key in INSURANCE_MARKER_KEYS:
            insurance_rows.append(row)
        elif fact_type == "coverage_fact":
            # Coverage rows are projected separately, but retaining them here
            # makes the domain detection auditable.
            insurance_rows.append(row)
        elif key in INSURANCE_VALUE_KEYS and (
            document.document_type == "insurance"
            or page in insurance_marker_pages
            or (page is None and fact_type == "linked_product")
        ):
            insurance_rows.append(row)

    return _rows_to_values(mortgage_rows), _rows_to_values(insurance_rows), has_insurance


def _decimal(value: object) -> Decimal | None:
    try:
        raw=str(value).strip().replace(" ","")
        if "," in raw and "." in raw:
            raw=raw.replace(".","").replace(",",".") if raw.rfind(",")>raw.rfind(".") else raw.replace(",","")
        elif "," in raw:
            raw=raw.replace(",",".")
        elif raw.count(".")>1:
            raw=raw.replace(".","")
        return Decimal(raw)
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
        (("viaje",), "travel"),
    )
    for terms, value in mappings:
        if any(term in name for term in terms):
            return value
    return "unknown"


def _canonical_insurance_type(value: object, file_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return _insurance_type(file_name)
    low = raw.lower()
    mappings = (
        (("hogar", "vivienda", "home"), "home"),
        (("coche", "auto", "vehiculo", "vehículo", "car"), "car"),
        (("vida", "life"), "life"),
        (("salud", "medico", "médico", "health"), "health"),
        (("mascota", "perro", "gato", "pet"), "pet"),
        (("viaje", "travel"), "travel"),
    )
    for terms, canonical in mappings:
        if any(term in low for term in terms):
            return canonical
    return raw[:60]


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
    if document.document_type not in CONTRACT_DOCUMENT_TYPES:
        return None
    if document.document_type=="mortgage" and _entity_link(session,document.id,"mortgage") is None:
        return None

    contract = None
    contract_links = session.scalars(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document.id,
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == "contract",
        )
    ).all()
    for candidate_link in contract_links:
        candidate = session.get(Contract, candidate_link.to_id)
        if candidate is not None and candidate.contract_type == document.document_type:
            contract = candidate
            break
    if contract is None and document.document_type=="insurance":
        policy_link=_entity_link(session,document.id,"insurance_policy")
        policy=session.get(InsurancePolicy,policy_link.to_id) if policy_link else None
        if policy is not None and policy.contract_id:
            contract=session.get(Contract,policy.contract_id)
            if contract is not None:
                _add_evidence_link(session,document.id,"contract",contract.id,confidence=Decimal("0.98"),source_type="policy_group")
    if contract is None and not values:
        return None
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

    contract.provider_name = str(values.get("provider_name",{}).get("value") or contract.provider_name or _label(document))[:180]
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
    if "start_date" in values:
        contract.start_date = _date(values["start_date"].get("value"))
    if "renewal_date" in values:
        contract.renewal_date = _date(values["renewal_date"].get("value"))
    elif document.document_type=="insurance" and "next_review_date" in values:
        contract.renewal_date = _date(values["next_review_date"].get("value"))
    if "permanence_end_date" in values:
        contract.permanence_end_date = _date(values["permanence_end_date"].get("value"))

    contract.evidence_status = (
        "confirmed"
        if summary["confirmed"] > 0 and summary["pending"] == 0 and summary["ambiguous"] == 0
        else "needs_more_data"
    )
    session.flush()
    return contract


def _interest_type(value: object) -> str | None:
    raw=str(value or "").strip().lower()
    if "variable" in raw:return "variable"
    if "mixt" in raw:return "mixed"
    if "fijo" in raw or "fixed" in raw:return "fixed"
    return None


def _ensure_mortgage_extra_projection(
    session: Session,
    mortgage: Mortgage,
    values: dict[str, dict],
) -> MortgageProfileExtra | None:
    """Project confirmed mortgage evidence into the extended profile.

    Document evidence fills gaps only: a previously entered profile value is not
    silently overwritten. Percentages used as rates are converted from the
    document's percent scale to the internal decimal scale; commission
    percentages keep their percent scale because cost engines divide by 100.
    """
    mapping_keys = {
        "apr_rate",
        "reference_index",
        "differential_rate",
        "mortgage_term_years",
        "rate_review_months",
        "next_review_date",
        "opening_fee_percent",
        "early_repayment_fee_percent",
        "subrogation_fee_percent",
        "cancellation_fee_percent",
    }
    if not any(key in values for key in mapping_keys):
        return session.scalar(
            select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id == mortgage.id)
        )

    row = session.scalar(
        select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id == mortgage.id)
    )
    if row is None:
        row = MortgageProfileExtra(mortgage_id=mortgage.id)
        session.add(row)
        session.flush()

    if row.apr_rate is None and "apr_rate" in values:
        pct = _decimal(values["apr_rate"].get("value"))
        if pct is not None:
            row.apr_rate = pct / Decimal("100")
    if not row.reference_index and "reference_index" in values:
        value = str(values["reference_index"].get("value") or "").strip()
        if value:
            row.reference_index = value[:80]
    if row.differential_rate is None and "differential_rate" in values:
        pct = _decimal(values["differential_rate"].get("value"))
        if pct is not None:
            row.differential_rate = pct / Decimal("100")
    if row.original_term_months is None and "mortgage_term_years" in values:
        years = _integer(values["mortgage_term_years"].get("value"))
        if years is not None and years > 0:
            row.original_term_months = years * 12
    if row.rate_review_months is None and "rate_review_months" in values:
        months = _integer(values["rate_review_months"].get("value"))
        if months is not None and months > 0:
            row.rate_review_months = months
    if row.next_review_date is None and "next_review_date" in values:
        row.next_review_date = _date(values["next_review_date"].get("value"))

    for key in (
        "opening_fee_percent",
        "early_repayment_fee_percent",
        "subrogation_fee_percent",
        "cancellation_fee_percent",
    ):
        if getattr(row, key) is not None or key not in values:
            continue
        pct = _decimal(values[key].get("value"))
        if pct is not None:
            setattr(row, key, pct)

    session.flush()
    return row


def _ensure_mortgage_projection(
    session: Session,
    document: Document,
    values: dict[str, dict],
) -> Mortgage | None:
    link=_entity_link(session,document.id,"mortgage")
    # Solo un vínculo explícito elegido por el usuario permite que un documento
    # hipotecario modifique la hipoteca actual. Las ofertas/FEIN comparativas
    # siguen siendo evidencia consultable pero no alteran el estado vigente.
    if link is None:
        return None
    mortgage=session.get(Mortgage,link.to_id)
    if mortgage is None:
        return None

    changed=False
    provider=str(values.get("provider_name",{}).get("value") or "").strip()
    if provider and mortgage.lender!=provider[:180]:
        mortgage.lender=provider[:180];changed=True
    if "remaining_principal" in values:
        principal=_decimal(values["remaining_principal"].get("value"))
        if principal is not None and mortgage.remaining_principal!=principal:
            mortgage.remaining_principal=principal;changed=True
    if "nominal_rate" in values:
        pct=_decimal(values["nominal_rate"].get("value"))
        rate=None if pct is None else pct/Decimal("100")
        if rate is not None and mortgage.nominal_rate!=rate:
            mortgage.nominal_rate=rate;changed=True
    if "monthly_payment" in values:
        payment=_decimal(values["monthly_payment"].get("value"))
        if payment is not None and mortgage.monthly_payment!=payment:
            mortgage.monthly_payment=payment;changed=True
    if "remaining_months" in values:
        months=_integer(values["remaining_months"].get("value"))
        if months is not None and months>0 and mortgage.remaining_months!=months:
            mortgage.remaining_months=months;changed=True
    if "interest_type" in values:
        kind=_interest_type(values["interest_type"].get("value"))
        if kind and mortgage.interest_type!=kind:
            mortgage.interest_type=kind;changed=True
    if "early_repayment_fee" in values:
        fee=_decimal(values["early_repayment_fee"].get("value"))
        if fee is not None and mortgage.early_repayment_fee!=fee:
            mortgage.early_repayment_fee=fee;changed=True

    _ensure_mortgage_extra_projection(session, mortgage, values)
    session.flush()
    if changed:
        from .snapshots import record_snapshot
        record_snapshot(session,"mortgage",mortgage.id,{
            "remaining_principal":str(mortgage.remaining_principal),
            "nominal_rate":str(mortgage.nominal_rate),
            "monthly_payment":str(mortgage.monthly_payment),
            "remaining_months":mortgage.remaining_months,
            "early_repayment_fee":None if mortgage.early_repayment_fee is None else str(mortgage.early_repayment_fee),
            "currency":mortgage.currency,
            "source_document_id":document.id,
        },source="document_evidence")
    return mortgage


def _ensure_insurance_projection(
    session: Session,
    document: Document,
    contract: Contract | None,
    values: dict[str, dict],
) -> InsurancePolicy | None:
    if document.document_type != "insurance":
        return None

    link = _entity_link(session, document.id, "insurance_policy")
    policy = session.get(InsurancePolicy, link.to_id) if link else None
    if contract is None and policy is not None and policy.contract_id:
        contract = session.get(Contract, policy.contract_id)
    if policy is None and contract is not None:
        policy = session.scalar(select(InsurancePolicy).where(InsurancePolicy.contract_id == contract.id))
        if policy is not None:
            _add_evidence_link(
                session, document.id, "insurance_policy", policy.id,
                confidence=Decimal("0.98"), source_type="policy_group",
            )

    premium = None
    if "annual_cost" in values:
        premium = _decimal(values["annual_cost"].get("value"))
    elif "monthly_cost" in values:
        monthly = _decimal(values["monthly_cost"].get("value"))
        premium = None if monthly is None else monthly * Decimal("12")

    # annual_premium is mandatory for creating a new policy. A document that
    # is already linked to an existing policy may contribute other evidence.
    if policy is None and (premium is None or contract is None):
        return None

    if policy is None:
        policy = InsurancePolicy(
            contract_id=contract.id,
            insurance_type=_canonical_insurance_type(values.get("insurance_type",{}).get("value"),document.file_name),
            annual_premium=premium,
            deductible=None,
            currency="EUR",
            insured_object_json="{}",
        )
        session.add(policy)
        session.flush()
        _add_evidence_link(
            session,
            document.id,
            "insurance_policy",
            policy.id,
            confidence=Decimal("1"),
            source_type="document_projection",
        )
        if contract is not None:
            for grouped_document_id in _linked_document_ids(session, "contract", contract.id):
                _add_evidence_link(
                    session, grouped_document_id, "insurance_policy", policy.id,
                    confidence=Decimal("0.98"), source_type="policy_group",
                )

    if contract is not None:
        policy.contract_id = contract.id
    policy_number = (
        values.get("policy_number",{}).get("value")
        or values.get("contract_number",{}).get("value")
    )
    if policy_number:
        policy.policy_number_masked=str(policy_number)[:80]
    if values.get("insurance_type",{}).get("value"):
        policy.insurance_type=_canonical_insurance_type(values["insurance_type"]["value"],document.file_name)
    if premium is not None:
        policy.annual_premium = premium
    if "deductible" in values:
        policy.deductible = _decimal(values["deductible"].get("value"))
    if values.get("insured_object",{}).get("value"):
        policy.insured_object_json=json.dumps(
            {"description":str(values["insured_object"]["value"])},
            ensure_ascii=False,
        )
    session.flush()
    return policy


def _insurance_contract_for_document(session: Session, document_id: str) -> Contract | None:
    links = session.scalars(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document_id,
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == "contract",
        )
    ).all()
    for link in links:
        contract = session.get(Contract, link.to_id)
        if contract is not None and contract.contract_type == "insurance":
            return contract
    return None


def _policy_by_confirmed_number(
    session: Session,
    policy_number: object,
) -> InsurancePolicy | None:
    normalized = _normalize_identity(policy_number)
    if not normalized:
        return None
    for policy in session.scalars(select(InsurancePolicy)).all():
        if _normalize_identity(policy.policy_number_masked) == normalized:
            return policy
    return None


def _ensure_mortgage_insurance_link(
    session: Session,
    mortgage: Mortgage | None,
    policy: InsurancePolicy | None,
    document: Document,
) -> None:
    if mortgage is None or policy is None:
        return
    existing = session.scalar(
        select(LinkedProduct).where(
            LinkedProduct.parent_product_type == "mortgage",
            LinkedProduct.parent_product_id == mortgage.id,
            LinkedProduct.linked_product_type == "insurance_policy",
            LinkedProduct.linked_product_id == policy.id,
        )
    )
    if existing is None:
        session.add(LinkedProduct(
            parent_product_type="mortgage",
            parent_product_id=mortgage.id,
            linked_product_type="insurance_policy",
            linked_product_id=policy.id,
            discount_value=Decimal("0"),
            discount_unit="currency",
            conditions=f"Vinculado por evidencia confirmada del documento {document.file_name}",
        ))
        session.flush()


def _ensure_embedded_insurance_projection(
    session: Session,
    document: Document,
    mortgage: Mortgage | None,
    values: dict[str, dict],
    summary: dict,
) -> tuple[Contract | None, InsurancePolicy | None]:
    """Project a confirmed insurance section embedded in another product PDF.

    The source document keeps its original classification (for example,
    mortgage), while the insurance facts become a real insurance policy with
    its own contract and evidence link.
    """
    if not values:
        return None, None

    policy_link = _entity_link(session, document.id, "insurance_policy")
    policy = session.get(InsurancePolicy, policy_link.to_id) if policy_link else None
    policy_number = (
        values.get("policy_number",{}).get("value")
        or values.get("contract_number",{}).get("value")
    )
    if policy is None and policy_number:
        policy = _policy_by_confirmed_number(session, policy_number)

    contract = (
        session.get(Contract, policy.contract_id)
        if policy is not None and policy.contract_id
        else _insurance_contract_for_document(session, document.id)
    )
    if contract is None:
        provider = str(values.get("provider_name",{}).get("value") or "").strip()
        contract = Contract(
            provider_name=(provider or f"{_label(document)} · seguro")[:180],
            contract_type="insurance",
            currency="EUR",
            evidence_status="needs_more_data",
        )
        session.add(contract)
        session.flush()
        _add_evidence_link(
            session, document.id, "contract", contract.id,
            confidence=Decimal("1"), source_type="embedded_insurance_projection",
        )

    provider = str(values.get("provider_name",{}).get("value") or "").strip()
    if provider:
        contract.provider_name = provider[:180]
    if "annual_cost" in values:
        contract.annual_cost = _decimal(values["annual_cost"].get("value"))
    elif "monthly_cost" in values:
        monthly = _decimal(values["monthly_cost"].get("value"))
        if monthly is not None:
            contract.annual_cost = monthly * Decimal("12")
    if "renewal_date" in values:
        contract.renewal_date = _date(values["renewal_date"].get("value"))
    elif "next_review_date" in values:
        contract.renewal_date = _date(values["next_review_date"].get("value"))
    if "start_date" in values:
        contract.start_date = _date(values["start_date"].get("value"))
    if "cancellation_notice_days" in values:
        contract.cancellation_notice_days = _integer(values["cancellation_notice_days"].get("value"))
    if "early_exit_penalty" in values:
        contract.early_exit_penalty = _decimal(values["early_exit_penalty"].get("value"))
    if "permanence_end_date" in values:
        contract.permanence_end_date = _date(values["permanence_end_date"].get("value"))
    contract.evidence_status = (
        "confirmed"
        if summary["confirmed"] > 0 and summary["pending"] == 0 and summary["ambiguous"] == 0
        else "needs_more_data"
    )

    premium = contract.annual_cost
    if policy is None and premium is None:
        # InsurancePolicy requires a real premium. Keep the insurance contract
        # as evidence, but never invent a 0 € policy.
        session.flush()
        return contract, None

    if policy is None:
        policy = InsurancePolicy(
            contract_id=contract.id,
            insurance_type=_canonical_insurance_type(
                values.get("insurance_type",{}).get("value"),
                document.file_name,
            ),
            annual_premium=premium,
            deductible=_decimal(values.get("deductible",{}).get("value")),
            currency="EUR",
            insured_object_json="{}",
        )
        session.add(policy)
        session.flush()
    else:
        policy.contract_id = contract.id
        if premium is not None:
            policy.annual_premium = premium

    if policy_number:
        policy.policy_number_masked = str(policy_number)[:80]
    if values.get("insurance_type",{}).get("value"):
        policy.insurance_type = _canonical_insurance_type(
            values["insurance_type"]["value"],
            document.file_name,
        )
    if "deductible" in values:
        policy.deductible = _decimal(values["deductible"].get("value"))
    if values.get("insured_object",{}).get("value"):
        policy.insured_object_json = json.dumps(
            {"description": str(values["insured_object"]["value"])},
            ensure_ascii=False,
        )

    _add_evidence_link(
        session, document.id, "insurance_policy", policy.id,
        confidence=Decimal("1"), source_type="embedded_insurance_projection",
    )
    _add_evidence_link(
        session, document.id, "contract", contract.id,
        confidence=Decimal("1"), source_type="embedded_insurance_projection",
    )
    _ensure_mortgage_insurance_link(session, mortgage, policy, document)
    session.flush()
    return contract, policy


def _ensure_coverage_projection(
    session: Session,
    document: Document,
    contract: Contract | None,
    policy: InsurancePolicy | None,
) -> int:
    if contract is None and policy is None:
        return 0

    rows = session.scalars(
        select(ExtractedFact).where(
            ExtractedFact.document_id == document.id,
            ExtractedFact.fact_type == "coverage_fact",
            ExtractedFact.status == "confirmed",
            ExtractedFact.user_verified.is_(True),
        )
    ).all()

    session.execute(
        delete(CoverageFact).where(CoverageFact.source_document_id == document.id)
    )

    created = 0
    for row in rows:
        payload = _payload(row)
        coverage_type = str(payload.get("coverage_type") or payload.get("value") or "").strip()
        if not coverage_type:
            continue
        limit_amount = _decimal(payload.get("limit_amount"))
        deductible = _decimal(payload.get("deductible"))
        conditions = str(payload.get("conditions") or "").strip()
        exclusions = str(payload.get("exclusions") or "").strip()
        session.add(
            CoverageFact(
                contract_id=None if contract is None else contract.id,
                insurance_policy_id=None if policy is None else policy.id,
                coverage_type=coverage_type[:100],
                limit_amount=limit_amount,
                deductible=deductible,
                conditions_json=json.dumps({"text":conditions},ensure_ascii=False) if conditions else "{}",
                exclusions_json=json.dumps({"text":exclusions},ensure_ascii=False) if exclusions else "{}",
                source_document_id=document.id,
                source_page=row.source_page,
                confidence=row.confidence,
                user_verified=True,
            )
        )
        created += 1
    session.flush()
    return created


def _reconcile_identity_siblings(session: Session, document: Document) -> int:
    identities=_identity_values(session,document.id)
    strong=[(key,identities.get(key)) for key in ("policy_number","contract_number") if identities.get(key)]
    if not strong:
        return 0
    changed=0
    for sibling in session.scalars(select(Document).where(Document.id!=document.id)).all():
        sibling_identities=_identity_values(session,sibling.id)
        if not any(sibling_identities.get(key)==value for key,value in strong):
            continue
        before={
            "insurance_policy":_entity_link(session,sibling.id,"insurance_policy"),
            "mortgage":_entity_link(session,sibling.id,"mortgage"),
            "contract":_entity_link(session,sibling.id,"contract"),
        }
        result=auto_link_document_entity(session,sibling)
        if result is None:
            continue
        if before.get(result["entity_type"]) is None:
            synchronize_document_evidence(session,sibling,reconcile_group=False)
            changed+=1
    return changed


def synchronize_document_evidence(
    session: Session, document: Document, reconcile_group: bool = True
) -> dict:
    auto_link_document_entity(session, document)
    summary = sync_review_action(session, document)
    confirmed_rows = _confirmed_fact_rows(session, document.id)
    all_values = _rows_to_values(confirmed_rows)
    mortgage_values, insurance_values, has_embedded_insurance = _partition_confirmed_values(
        document, confirmed_rows
    )

    primary_values = mortgage_values if document.document_type == "mortgage" else all_values
    contract = _ensure_contract_projection(session, document, primary_values, summary)
    mortgage = _ensure_mortgage_projection(session, document, mortgage_values if document.document_type == "mortgage" else all_values)

    insurance_contract = contract if document.document_type == "insurance" else None
    policy = _ensure_insurance_projection(session, document, insurance_contract, all_values)
    if document.document_type != "insurance" and has_embedded_insurance:
        insurance_contract, policy = _ensure_embedded_insurance_projection(
            session,
            document,
            mortgage,
            insurance_values,
            summary,
        )

    coverage_count = _ensure_coverage_projection(
        session, document, insurance_contract, policy
    )
    if contract is not None:
        from .contracts import refresh_contract_actions
        refresh_contract_actions(session)
    if insurance_contract is not None and insurance_contract is not contract:
        from .contracts import refresh_contract_actions
        refresh_contract_actions(session)
    if coverage_count:
        from .contracts import scan_coverage_overlaps
        scan_coverage_overlaps(session)
    grouped_documents=0
    if reconcile_group and (policy is not None or contract is not None or mortgage is not None):
        grouped_documents=_reconcile_identity_siblings(session,document)
    session.flush()
    return {
        **summary,
        "contract_id": None if contract is None else contract.id,
        "mortgage_id": None if mortgage is None else mortgage.id,
        "insurance_contract_id": None if insurance_contract is None else insurance_contract.id,
        "insurance_policy_id": None if policy is None else policy.id,
        "coverage_count": coverage_count,
        "grouped_documents": grouped_documents,
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
                    "fact_type": fact.fact_type,
                    "key": fact.key,
                    "value": payload.get("value"),
                    "unit": payload.get("unit"),
                    "status": fact.status,
                    "user_verified": fact.user_verified,
                    "confidence": str(fact.confidence),
                    "page": fact.source_page,
                    "source_section": fact.source_section,
                    "manual": fact.source_section=="Introducido por el usuario",
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
                    "ai_analysis": latest_analysis(session,document.id),
                }
            )
        if used >= max_facts:
            break
    return {
        "rule": "Solo status=confirmed y user_verified=true es evidencia confirmada para cálculos deterministas. inferred/ambiguous es contexto pendiente de revisión. ai_analysis es interpretación local para explicar y descubrir relaciones; nunca sustituye un hecho contractual confirmado.",
        "documents": out,
    }
