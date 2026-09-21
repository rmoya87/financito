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
from financito.models_extended import Asset, InsurancePolicy, MortgageProfileExtra
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
                "original_principal":"240000",
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
        assert Decimal(data["principal_progress"]["remaining_percent"])==Decimal("62.5")
        assert Decimal(data["principal_progress"]["paid_percent"])==Decimal("37.5")
        assert Decimal(data["principal_progress"]["paid_principal"])==Decimal("90000.00")


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
            early_repayment_fee=None,
        )
        db.add(mortgage);db.flush()
        db.add(MortgageProfileExtra(
            mortgage_id=mortgage.id,
            subrogation_fee_percent=Decimal("0.5"),
        ))
        db.commit()

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
        assert Decimal(lead["scenario"]["known_exit_penalty"])==Decimal("600.00")
        assert lead["scenario"]["break_even_months_known_penalty_only"] is not None


def test_confirmed_mortgage_document_projects_extended_profile_fields():
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender=f"Banco Evidencia {uuid4().hex[:6]}",
            remaining_principal=Decimal("110000"),
            currency="EUR",
            interest_type="variable",
            nominal_rate=Decimal("0.031"),
            monthly_payment=Decimal("650"),
            remaining_months=220,
        )
        db.add(mortgage);db.flush()
        document=_doc(db,"hipoteca-variable.pdf")
        document.document_type="mortgage"
        db.add(EntityLink(
            from_type="document",from_id=document.id,relation_type="evidence_for",
            to_type="mortgage",to_id=mortgage.id,confidence=Decimal("1"),
            source_type="user",source_ref=document.id,
        ))
        values={
            "start_date":"16/11/2015",
            "maturity_date":"16/11/2045",
            "apr_rate":"3.45",
            "reference_index":"Euríbor 12 meses",
            "differential_rate":"0.75",
            "mortgage_term_years":"30",
            "rate_review_months":"12",
            "next_review_date":"15/02/2027",
            "reference_index_lag_months":"2",
            "opening_fee_percent":"0.10",
            "early_repayment_fee_percent":"0.25",
            "subrogation_fee_percent":"0.50",
            "cancellation_fee_percent":"0.40",
        }
        for key,value in values.items():
            fact=_fact(db,document,key,value)
            fact.status="confirmed"
            fact.user_verified=True
        db.flush()

        synchronize_document_evidence(db,document)
        extra=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage.id))
        assert extra is not None
        assert str(extra.start_date)=="2015-11-16"
        assert str(extra.maturity_date)=="2045-11-16"
        assert extra.apr_rate==Decimal("0.0345")
        assert extra.reference_index=="Euríbor 12 meses"
        assert extra.differential_rate==Decimal("0.0075")
        assert extra.original_term_months==360
        assert extra.rate_review_months==12
        assert str(extra.next_review_date)=="2027-02-15"
        assert extra.opening_fee_percent==Decimal("0.10")
        assert extra.early_repayment_fee_percent==Decimal("0.25")
        assert extra.subrogation_fee_percent==Decimal("0.50")
        assert extra.cancellation_fee_percent==Decimal("0.40")
        from financito.services.mortgage_cost import rate_review_readiness
        readiness=rate_review_readiness(db,mortgage)
        assert readiness["status"]=="ready"
        assert readiness["reference_index_lag_months"]==2


def test_mortgage_context_keeps_found_unverified_fact_out_of_missing_truth():
    from financito.services.contractual_costs import mortgage_contract_context

    with SessionLocal() as db:
        mortgage=Mortgage(
            lender=f"Banco Pendiente {uuid4().hex[:6]}",
            remaining_principal=Decimal("90000"),
            currency="EUR",
            interest_type="variable",
            nominal_rate=Decimal("0.029"),
            monthly_payment=Decimal("550"),
            remaining_months=180,
        )
        db.add(mortgage);db.flush()
        document=_doc(db,"hipoteca-pendiente.pdf")
        document.document_type="mortgage"
        db.add(EntityLink(
            from_type="document",from_id=document.id,relation_type="evidence_for",
            to_type="mortgage",to_id=mortgage.id,confidence=Decimal("1"),
            source_type="user",source_ref=document.id,
        ))
        fact=_fact(db,document,"differential_rate","0.60")
        fact.value_json=json.dumps({"value":"0.60","unit":"percent","source":"local_ai_proposal"})
        db.flush()

        context=mortgage_contract_context(db,mortgage.id)
        assert "differential_rate" not in context["by_key"]
        assert context["pending_by_key"]["differential_rate"]["value"]=="0.60"
        assert context["pending_by_key"]["differential_rate"]["source"]=="local_ai_proposal"


def test_insurance_verdict_surfaces_ai_found_terms_as_pending_review():
    from financito.services.insurance_analysis import insurance_verdict

    with SessionLocal() as db:
        contract=Contract(
            provider_name=f"Seguro IA {uuid4().hex[:6]}",
            contract_type="insurance",
            annual_cost=Decimal("480"),
            evidence_status="needs_more_data",
        )
        db.add(contract);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,
            insurance_type="home",
            annual_premium=Decimal("480"),
            deductible=None,
            currency="EUR",
            insured_object_json="{}",
        )
        db.add(policy);db.flush()
        document=_doc(db,"seguro-ia.pdf")
        for target_type,target_id in (("contract",contract.id),("insurance_policy",policy.id)):
            db.add(EntityLink(
                from_type="document",from_id=document.id,relation_type="evidence_for",
                to_type=target_type,to_id=target_id,confidence=Decimal("1"),
                source_type="user",source_ref=document.id,
            ))
        for key,value,unit in (
            ("deductible","150","EUR"),
            ("renewal_date","01/06/2027","date"),
            ("cancellation_notice_days","30","days"),
            ("early_exit_penalty","0","EUR"),
        ):
            fact=_fact(db,document,key,value)
            fact.value_json=json.dumps({"value":value,"unit":unit,"source":"local_ai_proposal"})
        db.flush()

        result=insurance_verdict(db,use_ai=False)
        pending=[x for x in result["pending_review"] if x.get("policy_id")==policy.id]
        fields={x["field"] for x in pending}
        assert {"deductible","renewal_date","cancellation_notice_days","early_exit_penalty"} <= fields
        missing_fields={x["field"] for x in result["missing_information"] if x.get("policy_id")==policy.id}
        assert "deductible" not in missing_fields
        assert "renewal_date" not in missing_fields


def test_wealth_home_can_select_between_multiple_mortgages():
    with SessionLocal() as db:
        first=Mortgage(
            lender=f"Banco A {uuid4().hex[:6]}",
            remaining_principal=Decimal("100000"),currency="EUR",interest_type="fixed",
            nominal_rate=Decimal("0.03"),monthly_payment=Decimal("600"),remaining_months=180,
        )
        second=Mortgage(
            lender=f"Banco B {uuid4().hex[:6]}",
            remaining_principal=Decimal("200000"),currency="EUR",interest_type="variable",
            nominal_rate=Decimal("0.04"),monthly_payment=Decimal("1000"),remaining_months=240,
        )
        db.add_all([first,second]);db.commit()
        first_id=first.id;second_id=second.id

    with TestClient(app) as client:
        client.get("/api/v1/session")
        first_response=client.get("/api/v1/wealth/home",params={"mortgage_id":first_id})
        second_response=client.get("/api/v1/wealth/home",params={"mortgage_id":second_id})
        assert first_response.status_code==200
        assert second_response.status_code==200
        assert first_response.json()["mortgage"]["id"]==first_id
        assert second_response.json()["mortgage"]["id"]==second_id


def test_deleting_mortgage_unlinks_documents_but_keeps_files():
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender=f"Banco borrar {uuid4().hex[:6]}",
            remaining_principal=Decimal("80000"),currency="EUR",interest_type="fixed",
            nominal_rate=Decimal("0.025"),monthly_payment=Decimal("500"),remaining_months=160,
        )
        db.add(mortgage);db.flush()
        document=_doc(db,"hipoteca-borrar.pdf")
        document.document_type="mortgage"
        db.add(EntityLink(
            from_type="document",from_id=document.id,relation_type="evidence_for",
            to_type="mortgage",to_id=mortgage.id,confidence=Decimal("1"),
            source_type="user",source_ref=document.id,
        ))
        db.commit();mortgage_id=mortgage.id;document_id=document.id

    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        response=client.delete(f"/api/v1/mortgages/{mortgage_id}",headers={"X-CSRF-Token":session.json()["csrf_token"]})
        assert response.status_code==200

    with SessionLocal() as db:
        assert db.get(Mortgage,mortgage_id) is None
        assert db.get(Document,document_id) is not None
        assert db.scalar(select(EntityLink.id).where(
            EntityLink.from_type=="document",EntityLink.from_id==document_id,
            EntityLink.to_type=="mortgage",EntityLink.to_id==mortgage_id,
        )) is None


def test_insurance_profile_crud_includes_category_contract_and_safe_document_unlink():
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        created=client.post("/api/v1/insurance",headers=headers,json={
            "provider_name":"Aseguradora Unit",
            "insurance_type":"car",
            "annual_premium":"420",
            "deductible":"200",
            "currency":"EUR",
            "policy_number_masked":"POL-123",
            "renewal_date":"2027-05-01",
            "cancellation_notice_days":30,
            "early_exit_penalty":"25",
            "contract_id":None,
        })
        assert created.status_code==200
        policy=created.json()
        policy_id=policy["id"]
        assert policy["insurance_type"]=="car"
        assert policy["provider_name"]=="Aseguradora Unit"
        assert policy["renewal_date"]=="2027-05-01"

        updated=client.patch(f"/api/v1/insurance/{policy_id}",headers=headers,json={
            "provider_name":"Aseguradora Editada",
            "insurance_type":"home",
            "annual_premium":"500",
            "deductible":"150",
            "currency":"EUR",
            "policy_number_masked":"POL-123",
            "renewal_date":"2027-06-01",
            "cancellation_notice_days":45,
            "early_exit_penalty":"10",
            "contract_id":None,
        })
        assert updated.status_code==200
        assert updated.json()["insurance_type"]=="home"
        assert updated.json()["provider_name"]=="Aseguradora Editada"
        assert updated.json()["cancellation_notice_days"]==45

    with SessionLocal() as db:
        document=_doc(db,"seguro-contextual.pdf")
        document.document_type="insurance"
        db.add(EntityLink(
            from_type="document",from_id=document.id,relation_type="evidence_for",
            to_type="insurance_policy",to_id=policy_id,confidence=Decimal("1"),
            source_type="user",source_ref=document.id,
        ))
        db.commit();document_id=document.id

    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        filtered=client.get("/api/v1/documents",params={"entity_type":"insurance_policy","entity_id":policy_id})
        assert filtered.status_code==200
        assert [row["id"] for row in filtered.json()]==[document_id]
        deleted=client.delete(f"/api/v1/insurance/{policy_id}",headers={"X-CSRF-Token":session.json()["csrf_token"]})
        assert deleted.status_code==200

    with SessionLocal() as db:
        assert db.get(InsurancePolicy,policy_id) is None
        assert db.get(Document,document_id) is not None
        assert db.scalar(select(EntityLink.id).where(
            EntityLink.from_type=="document",EntityLink.from_id==document_id,
            EntityLink.to_type=="insurance_policy",EntityLink.to_id==policy_id,
        )) is None


def test_contextual_document_list_only_returns_selected_product():
    with SessionLocal() as db:
        first=Mortgage(
            lender=f"Filtro A {uuid4().hex[:6]}",remaining_principal=Decimal("70000"),
            currency="EUR",interest_type="fixed",nominal_rate=Decimal("0.02"),
            monthly_payment=Decimal("450"),remaining_months=150,
        )
        second=Mortgage(
            lender=f"Filtro B {uuid4().hex[:6]}",remaining_principal=Decimal("90000"),
            currency="EUR",interest_type="fixed",nominal_rate=Decimal("0.025"),
            monthly_payment=Decimal("550"),remaining_months=170,
        )
        db.add_all([first,second]);db.flush()
        first_doc=_doc(db,"first-mortgage.pdf");first_doc.document_type="mortgage"
        second_doc=_doc(db,"second-mortgage.pdf");second_doc.document_type="mortgage"
        db.add_all([
            EntityLink(from_type="document",from_id=first_doc.id,relation_type="evidence_for",to_type="mortgage",to_id=first.id,confidence=Decimal("1"),source_type="user",source_ref=first_doc.id),
            EntityLink(from_type="document",from_id=second_doc.id,relation_type="evidence_for",to_type="mortgage",to_id=second.id,confidence=Decimal("1"),source_type="user",source_ref=second_doc.id),
        ])
        db.commit();first_id=first.id;first_doc_id=first_doc.id

    with TestClient(app) as client:
        client.get("/api/v1/session")
        response=client.get("/api/v1/documents",params={"entity_type":"mortgage","entity_id":first_id})
        assert response.status_code==200
        ids={row["id"] for row in response.json()}
        assert ids=={first_doc_id}
