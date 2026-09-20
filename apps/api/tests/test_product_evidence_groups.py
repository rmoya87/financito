from decimal import Decimal
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from financito.db import SessionLocal
from financito.main import app
from financito.models import Contract, Document, ExtractedFact
from financito.models_analytics import EntityLink
from financito.models_extended import InsurancePolicy
from financito.services.evidence import (
    auto_link_document_entity,
    confirm_entity_coherent_evidence,
)


def _document(db, name: str) -> Document:
    row=Document(
        file_path=f"/tmp/{uuid4().hex}-{name}",
        file_name=name,
        sha256=uuid4().hex+uuid4().hex,
        document_type="insurance",
        status="indexed",
        page_count=1,
        extracted_text="",
    )
    db.add(row);db.flush()
    return row


def _fact(db, document_id: str, key: str, value: str, *, status="inferred", verified=False, confidence="0.90"):
    row=ExtractedFact(
        document_id=document_id,
        fact_type="contract_term",
        key=key,
        value_json=json.dumps({"value":value}),
        confidence=Decimal(confidence),
        status=status,
        source_page=1,
        user_verified=verified,
    )
    db.add(row);db.flush()
    return row


def _policy_group(db):
    contract=Contract(
        provider_name=f"Aseguradora {uuid4().hex[:8]}",
        contract_type="insurance",
        annual_cost=Decimal("240"),
        evidence_status="confirmed",
    )
    db.add(contract);db.flush()
    policy=InsurancePolicy(
        contract_id=contract.id,
        policy_number_masked="POL-UNIT-123",
        insurance_type="home",
        annual_premium=Decimal("240"),
        currency="EUR",
        insured_object_json="{}",
    )
    db.add(policy);db.flush()
    return contract,policy


def test_second_document_with_same_policy_number_reuses_existing_policy():
    with SessionLocal() as db:
        contract,policy=_policy_group(db)
        first=_document(db,"condiciones-particulares.pdf")
        second=_document(db,"nota-mediador.pdf")
        for document in (first,second):
            _fact(db,document.id,"policy_number","POL-UNIT-123")
        db.add(EntityLink(
            from_type="document",from_id=first.id,relation_type="evidence_for",
            to_type="insurance_policy",to_id=policy.id,confidence=Decimal("1"),
            source_type="document_projection",source_ref=first.id,
        ))
        db.add(EntityLink(
            from_type="document",from_id=first.id,relation_type="evidence_for",
            to_type="contract",to_id=contract.id,confidence=Decimal("1"),
            source_type="document_projection",source_ref=first.id,
        ))
        db.flush()

        result=auto_link_document_entity(db,second)
        assert result is not None
        assert result["entity_type"]=="insurance_policy"
        assert result["entity_id"]==policy.id
        link=db.scalar(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.from_id==second.id,
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="insurance_policy",
        ))
        assert link is not None
        assert link.to_id==policy.id


def test_group_bulk_confirmation_confirms_only_coherent_values():
    with SessionLocal() as db:
        contract,policy=_policy_group(db)
        first=_document(db,"poliza-base.pdf")
        second=_document(db,"anexo-poliza.pdf")
        for document in (first,second):
            db.add(EntityLink(
                from_type="document",from_id=document.id,relation_type="evidence_for",
                to_type="insurance_policy",to_id=policy.id,confidence=Decimal("1"),
                source_type="user",source_ref=document.id,
            ))
            db.add(EntityLink(
                from_type="document",from_id=document.id,relation_type="evidence_for",
                to_type="contract",to_id=contract.id,confidence=Decimal("1"),
                source_type="user",source_ref=document.id,
            ))
        _fact(db,first.id,"provider_name","Aseguradora Unica",status="confirmed",verified=True)
        coherent=_fact(db,second.id,"provider_name","Aseguradora Unica")
        _fact(db,first.id,"annual_cost","240",status="confirmed",verified=True)
        conflict=_fact(db,second.id,"annual_cost","300")
        db.flush()

        result=confirm_entity_coherent_evidence(db,"insurance_policy",policy.id)
        assert result["documents"]==2
        assert result["confirmed"]>=1
        assert result["conflicts"]>=1
        assert coherent.status=="confirmed"
        assert coherent.user_verified is True
        assert conflict.status=="conflicting"
        assert conflict.user_verified is False


def test_general_contracts_endpoint_excludes_insurance_and_mortgage_types():
    with SessionLocal() as db:
        insurance=Contract(provider_name=f"INS-{uuid4().hex[:6]}",contract_type="insurance")
        mortgage=Contract(provider_name=f"MORT-{uuid4().hex[:6]}",contract_type="mortgage")
        service=Contract(provider_name=f"TEL-{uuid4().hex[:6]}",contract_type="telecom")
        db.add_all([insurance,mortgage,service]);db.commit()
        insurance_id=insurance.id;mortgage_id=mortgage.id;service_id=service.id

    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code==200
        response=client.get("/api/v1/contracts")
        assert response.status_code==200
        ids={row["id"] for row in response.json()}
        assert service_id in ids
        assert insurance_id not in ids
        assert mortgage_id not in ids


def test_dashboard_accepts_explicit_date_range():
    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code==200
        response=client.get("/api/v1/dashboard",params={"start":"2040-01-01","end":"2040-01-31"})
        assert response.status_code==200
        assert response.json()["period"]=={"start":"2040-01-01","end":"2040-01-31"}


def test_documents_can_group_by_policy_number_before_premium_is_confirmed():
    with SessionLocal() as db:
        first=_document(db,"seguro-info-1.pdf")
        second=_document(db,"seguro-info-2.pdf")
        _fact(db,first.id,"policy_number","POL-PENDING-777")
        _fact(db,second.id,"policy_number","POL-PENDING-777")
        db.flush()

        first_group=auto_link_document_entity(db,first)
        second_group=auto_link_document_entity(db,second)
        assert first_group is not None
        assert second_group is not None
        assert first_group["entity_type"]=="contract"
        assert second_group["entity_type"]=="contract"
        assert first_group["entity_id"]==second_group["entity_id"]

        contract=db.get(Contract,first_group["entity_id"])
        assert contract is not None
        assert contract.contract_type=="insurance"
        assert contract.annual_cost is None
        assert db.scalar(select(InsurancePolicy.id).where(InsurancePolicy.contract_id==contract.id)) is None
