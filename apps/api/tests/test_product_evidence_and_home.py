from datetime import date
from decimal import Decimal
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from financito.db import SessionLocal
from financito.main import app
from financito.models import Contract, Document, ExtractedFact, Mortgage
from financito.models_analytics import EntityLink
from financito.models_extended import Asset, InsurancePolicy
from financito.services.evidence import (
    confirm_entity_coherent_evidence,
    synchronize_document_evidence,
)
from financito.services.market_research import scan_public_market


def _sha():
    return (uuid4().hex + uuid4().hex)[:64]


def _doc(db, name):
    row=Document(
        file_path=f"/tmp/{uuid4().hex}-{name}",
        file_name=name,
        sha256=_sha(),
        document_type="insurance",
        status="indexed",
        page_count=1,
        extracted_text="",
    )
    db.add(row);db.flush();return row


def _fact(db, doc, key, value, confidence="0.95"):
    row=ExtractedFact(
        document_id=doc.id,
        fact_type="contract_term",
        key=key,
        value_json=json.dumps({"value":value}),
        confidence=Decimal(confidence),
        status="inferred",
        source_page=1,
        user_verified=False,
    )
    db.add(row);db.flush();return row


def test_same_policy_number_auto_groups_multiple_documents():
    with SessionLocal() as db:
        contract=Contract(provider_name=f"Aseguradora {uuid4().hex[:6]}",contract_type="insurance")
        db.add(contract);db.flush()
        policy=InsurancePolicy(contract_id=contract.id,insurance_type="home",annual_premium=Decimal("600"),currency="EUR")
        db.add(policy);db.flush()

        first=_doc(db,"poliza-principal.pdf")
        second=_doc(db,"anexo-poliza.pdf")
        _fact(db,first,"policy_number","POL-ABC-12345")
        _fact(db,second,"policy_number","POL-ABC-12345")

        db.add(EntityLink(from_type="document",from_id=first.id,relation_type="evidence_for",to_type="insurance_policy",to_id=policy.id,confidence=Decimal("1"),source_type="user",source_ref=first.id))
        db.add(EntityLink(from_type="document",from_id=first.id,relation_type="evidence_for",to_type="contract",to_id=contract.id,confidence=Decimal("1"),source_type="user",source_ref=first.id))
        db.flush()

        synchronize_document_evidence(db,second)
        policy_link=db.scalar(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.from_id==second.id,
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="insurance_policy",
            EntityLink.to_id==policy.id,
        ))
        contract_link=db.scalar(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.from_id==second.id,
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="contract",
            EntityLink.to_id==contract.id,
        ))
        assert policy_link is not None
        assert contract_link is not None


def test_group_confirmation_confirms_equal_values_and_leaves_conflicts_pending():
    with SessionLocal() as db:
        contract=Contract(provider_name=f"Seguro Group {uuid4().hex[:6]}",contract_type="insurance")
        db.add(contract);db.flush()
        policy=InsurancePolicy(contract_id=contract.id,insurance_type="home",annual_premium=Decimal("1"),currency="EUR")
        db.add(policy);db.flush()

        first=_doc(db,"condiciones.pdf")
        second=_doc(db,"recibo.pdf")
        for doc in (first,second):
            db.add(EntityLink(from_type="document",from_id=doc.id,relation_type="evidence_for",to_type="insurance_policy",to_id=policy.id,confidence=Decimal("1"),source_type="user",source_ref=doc.id))
            db.add(EntityLink(from_type="document",from_id=doc.id,relation_type="evidence_for",to_type="contract",to_id=contract.id,confidence=Decimal("1"),source_type="user",source_ref=doc.id))
        annual_a=_fact(db,first,"annual_cost","600")
        annual_b=_fact(db,second,"annual_cost","600")
        deductible_a=_fact(db,first,"deductible","100")
        deductible_b=_fact(db,second,"deductible","200")
        db.flush()

        result=confirm_entity_coherent_evidence(db,"insurance_policy",policy.id)
        assert result["documents"]==2
        assert result["confirmed"]>=2
        assert result["conflicts"]==2
        assert annual_a.status=="confirmed" and annual_a.user_verified is True
        assert annual_b.status=="confirmed" and annual_b.user_verified is True
        assert deductible_a.status=="conflicting" and deductible_a.user_verified is False
        assert deductible_b.status=="conflicting" and deductible_b.user_verified is False
        assert policy.annual_premium==Decimal("600")


def test_casa_endpoint_and_extra_profile_support_mortgage_optimization_fields():
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender=f"Banco Casa {uuid4().hex[:6]}",
            remaining_principal=Decimal("150000"),
            currency="EUR",
            interest_type="variable",
            nominal_rate=Decimal("0.035"),
            monthly_payment=Decimal("900"),
            remaining_months=240,
            early_repayment_fee=Decimal("120"),
        )
        db.add(mortgage);db.flush()
        home=Asset(
            asset_type="property",
            name=f"Vivienda {uuid4().hex[:6]}",
            current_value=Decimal("300000"),
            currency="EUR",
            valuation_date=date.today(),
            valuation_source="manual",
            ownership_type="personal",
            ownership_percentage=Decimal("100"),
        )
        db.add(home);db.commit()
        mortgage_id=mortgage.id

    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        saved=client.patch(
            f"/api/v1/mortgages/{mortgage_id}/profile-extra",
            headers=headers,
            json={
                "apr_rate":"0.038",
                "reference_index":"Euríbor 12m",
                "differential_rate":"0.009",
                "rate_review_months":12,
                "subrogation_fee_percent":"0.5",
            },
        )
        assert saved.status_code==200
        response=client.get("/api/v1/wealth/home")
        assert response.status_code==200
        data=response.json()
        assert data["mortgage"]["id"]==mortgage_id
        assert data["property"] is not None
        assert Decimal(data["ltv"])==Decimal("50.00")
        assert data["extra"]["reference_index"]=="Euríbor 12m"
        assert Decimal(data["extra"]["apr_rate"])==Decimal("0.038")


def test_market_scan_calculates_comparable_payment_without_network(monkeypatch):
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender=f"Banco Market {uuid4().hex[:6]}",
            remaining_principal=Decimal("120000"),
            currency="EUR",
            interest_type="fixed",
            nominal_rate=Decimal("0.04"),
            monthly_payment=Decimal("900"),
            remaining_months=180,
            early_repayment_fee=Decimal("100"),
        )
        db.add(mortgage);db.commit()

        def fake_scan(source, client):
            return {
                **source,
                "status":"ok",
                "retrieved_at":"2040-01-01T00:00:00+00:00",
                "rates":[{"type":"TIN","value_percent":"2.5"}] if source["id"]=="santander_fixed" else [],
                "claims":[],
                "promo_percent":None,
                "requires_personalized_quote":True,
            }

        monkeypatch.setattr("financito.services.market_research._scan_source",fake_scan)
        result=scan_public_market(db)
        lead=next(x for x in result["leads"] if x["source_id"]=="santander_fixed")
        assert lead["public_tin_min"]==2.5
        assert lead["scenario"] is not None
        assert Decimal(lead["scenario"]["estimated_payment"])>0
        assert Decimal(lead["scenario"]["monthly_payment_difference"])>0
        assert lead["scenario"]["known_exit_penalty"]=="100"
