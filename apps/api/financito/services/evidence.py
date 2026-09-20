from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re

from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..models import ActionItem, Contract, Document, ExtractedFact, Mortgage
from ..models_analytics import EntityLink
from ..models_extended import CoverageFact,InsurancePolicy
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

    A policy/contract number may create a lightweight Contract shell used only
    as an evidence group. It does not confirm premium, dates or conditions.
    """
    if document.document_type not in {"insurance", "contract", "loan", "energy", "telecom"}:
        return None

    policy_link = _entity_link(session, document.id, "insurance_policy")
    if policy_link is not None:
        return {"entity_type": "insurance_policy", "entity_id": policy_link.to_id, "matched_by": "existing_link"}
    contract_link = _entity_link(session, document.id, "contract")
    if contract_link is not None:
        return {"entity_type": "contract", "entity_id": contract_link.to_id, "matched_by": "existing_link"}

    identities = _identity_values(session, document.id)
    strong_key = "policy_number" if document.document_type == "insurance" else "contract_number"
    value = identities.get(strong_key)
    if not value:
        return None

    other_facts = session.scalars(
        select(ExtractedFact).where(
            ExtractedFact.document_id != document.id,
            ExtractedFact.key == strong_key,
        )
    ).all()
    for fact in other_facts:
        if _normalize_identity(_payload(fact).get("value")) != value:
            continue
        if document.document_type == "insurance":
            link = _entity_link(session, fact.document_id, "insurance_policy")
            if link is not None:
                _add_evidence_link(
                    session, document.id, "insurance_policy", link.to_id,
                    confidence=Decimal("0.98"), source_type="document_identity",
                )
                policy = session.get(InsurancePolicy, link.to_id)
                if policy and policy.contract_id:
                    _add_evidence_link(
                        session, document.id, "contract", policy.contract_id,
                        confidence=Decimal("0.98"), source_type="document_identity",
                    )
                return {"entity_type": "insurance_policy", "entity_id": link.to_id, "matched_by": strong_key}

        link = _entity_link(session, fact.document_id, "contract")
        if link is not None:
            contract = session.get(Contract, link.to_id)
            if contract is not None and (
                document.document_type != "insurance" or contract.contract_type == "insurance"
            ):
                _add_evidence_link(
                    session, document.id, "contract", contract.id,
                    confidence=Decimal("0.98"), source_type="document_identity",
                )
                return {"entity_type": "contract", "entity_id": contract.id, "matched_by": strong_key}

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
    return {"entity_type": "contract", "entity_id": contract.id, "matched_by": strong_key}



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
    if document.document_type not in CONTRACT_DOCUMENT_TYPES:
        return None
    if document.document_type=="mortgage" and _entity_link(session,document.id,"mortgage") is None:
        return None

    link = _entity_link(session, document.id, "contract")
    contract = session.get(Contract, link.to_id) if link else None
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


def _interest_type(value: object) -> str | None:
    raw=str(value or "").strip().lower()
    if "variable" in raw:return "variable"
    if "mixt" in raw:return "mixed"
    if "fijo" in raw or "fixed" in raw:return "fixed"
    return None


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
            insurance_type=str(values.get("insurance_type",{}).get("value") or _insurance_type(document.file_name))[:60],
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
        if contract is not None:
            for grouped_document_id in _linked_document_ids(session, "contract", contract.id):
                _add_evidence_link(
                    session, grouped_document_id, "insurance_policy", policy.id,
                    confidence=Decimal("0.98"), source_type="policy_group",
                )

    if contract is not None:
        policy.contract_id = contract.id
    if values.get("policy_number",{}).get("value"):
        policy.policy_number_masked=str(values["policy_number"]["value"])[:80]
    if values.get("insurance_type",{}).get("value"):
        policy.insurance_type=str(values["insurance_type"]["value"])[:60]
    if premium is not None:
        policy.annual_premium = premium
    if "deductible" in values:
        policy.deductible = _decimal(values["deductible"].get("value"))
    session.flush()
    return policy


def _ensure_coverage_projection(
    session: Session,
    document: Document,
    contract: Contract | None,
    policy: InsurancePolicy | None,
) -> int:
    if document.document_type != "insurance" or (contract is None and policy is None):
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


def synchronize_document_evidence(session: Session, document: Document) -> dict:
    auto_link_document_entity(session, document)
    summary = sync_review_action(session, document)
    values = _confirmed_values(session, document.id)
    contract = _ensure_contract_projection(session, document, values, summary)
    mortgage = _ensure_mortgage_projection(session, document, values)
    policy = _ensure_insurance_projection(session, document, contract, values)
    coverage_count = _ensure_coverage_projection(session, document, contract, policy)
    if contract is not None:
        from .contracts import refresh_contract_actions
        refresh_contract_actions(session)
    if coverage_count:
        from .contracts import scan_coverage_overlaps
        scan_coverage_overlaps(session)
    session.flush()
    return {
        **summary,
        "contract_id": None if contract is None else contract.id,
        "mortgage_id": None if mortgage is None else mortgage.id,
        "insurance_policy_id": None if policy is None else policy.id,
        "coverage_count": coverage_count,
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
