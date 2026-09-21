from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete,select

from financito.db import SessionLocal
from financito.models import Account,Contract,Document,ExtractedFact,Mortgage,Transaction
from financito.models_analytics import EntityLink,EntitySnapshot,LinkedProduct
from financito.models_extended import Asset,CoverageFact,InsurancePolicy,Liability
from financito.routes_extended import delete_insurance,delete_liability,link_mortgage_insurance,unlink_mortgage_insurance,wealth_details,wealth_home
from financito.routes_transactions import link_transaction_insurance,transaction_page,unlink_transaction_insurance
from financito.services.evidence import synchronize_all_document_evidence
from financito.services.insurance_analysis import insurance_verdict
from financito.services.snapshots import record_snapshot


def test_wealth_details_reports_asset_value_evolution_and_liability_can_be_deleted():
    with SessionLocal() as db:
        asset=Asset(
            asset_type="vehicle",name="Coche evolución test",current_value=Decimal("30000"),
            currency="EUR",valuation_date=date(2025,1,1),valuation_source="manual",
            ownership_type="personal",ownership_percentage=Decimal("100"),
        )
        debt=Liability(
            liability_type="loan",name="Préstamo borrar test",outstanding_amount=Decimal("5000"),
            currency="EUR",ownership_percentage=Decimal("100"),
        )
        db.add_all([asset,debt]);db.flush()
        record_snapshot(db,"asset",asset.id,{"value":"30000","ownership_percentage":"100","currency":"EUR"},date(2025,1,1),"test")
        asset.current_value=Decimal("24000")
        asset.valuation_date=date(2026,1,1)
        record_snapshot(db,"asset",asset.id,{"value":"24000","ownership_percentage":"100","currency":"EUR"},date(2026,1,1),"test")
        db.commit()

        data=wealth_details(db)
        row=next(item for item in data["assets"] if item["id"]==asset.id)
        assert Decimal(row["previous_value"])==Decimal("30000")
        assert Decimal(row["change_amount"])==Decimal("-6000.00")
        assert Decimal(row["change_pct"])==Decimal("-20.00")

        debt_id=debt.id
        result=delete_liability(debt_id,db)
        assert result["deleted"] is True
        assert db.scalar(select(Liability.id).where(Liability.id==debt_id)) is None
        snapshot=db.scalar(select(EntitySnapshot).where(
            EntitySnapshot.entity_type=="liability",
            EntitySnapshot.entity_id==debt_id,
        ).order_by(EntitySnapshot.as_of_date.desc()))
        assert snapshot is not None

        db.execute(delete(EntitySnapshot).where(EntitySnapshot.entity_type=="asset",EntitySnapshot.entity_id==asset.id))
        db.execute(delete(EntitySnapshot).where(EntitySnapshot.entity_type=="liability",EntitySnapshot.entity_id==debt_id))
        db.delete(asset);db.commit()


def test_insurance_verdict_exposes_contract_conditions_coverages_and_exclusions():
    with SessionLocal() as db:
        contract=Contract(
            provider_name="Aseguradora detalle test",contract_type="insurance",
            start_date=date(2026,1,1),renewal_date=date(2027,1,1),
            cancellation_notice_days=30,permanence_end_date=date(2026,12,31),
            early_exit_penalty=Decimal("80"),annual_cost=Decimal("480"),
            currency="EUR",evidence_status="manual",
        )
        db.add(contract);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,policy_number_masked="TEST-123",insurance_type="home",
            annual_premium=Decimal("480"),deductible=Decimal("150"),currency="EUR",
            insured_object_json='{"address":"Vivienda test","use":"habitual"}',
        )
        db.add(policy);db.flush()
        coverage=CoverageFact(
            contract_id=contract.id,insurance_policy_id=policy.id,coverage_type="Daños por agua",
            limit_amount=Decimal("15000"),deductible=Decimal("100"),
            conditions_json='{"condition":"mantenimiento adecuado"}',
            exclusions_json='{"exclusion":"falta de mantenimiento"}',
            effective_from=date(2026,1,1),effective_to=date(2026,12,31),
            confidence=Decimal("1"),user_verified=True,
        )
        db.add(coverage);db.commit()

        result=insurance_verdict(db,use_ai=False)
        row=next(item for item in result["policies"] if item["id"]==policy.id)
        assert row["policy_number_masked"]=="TEST-123"
        assert row["insured_object"]["address"]=="Vivienda test"
        assert row["contract"]["start_date"]=="2026-01-01"
        assert row["contract"]["permanence_end_date"]=="2026-12-31"
        assert row["contract"]["cancellation_notice_days"]==30
        assert row["coverages"][0]["conditions"]["condition"]=="mantenimiento adecuado"
        assert row["coverages"][0]["exclusions"]["exclusion"]=="falta de mantenimiento"
        assert row["coverages"][0]["effective_to"]=="2026-12-31"

        db.execute(delete(CoverageFact).where(CoverageFact.id==coverage.id))
        db.delete(policy);db.delete(contract);db.commit()



def test_life_insurance_can_be_explicitly_linked_to_mortgage_and_appears_in_casa():
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender="Banco vínculo seguro test",remaining_principal=Decimal("95000"),
            currency="EUR",interest_type="fixed",nominal_rate=Decimal("0.025"),
            monthly_payment=Decimal("600"),remaining_months=180,
        )
        contract=Contract(
            provider_name="Vida vínculo test",contract_type="insurance",
            annual_cost=Decimal("300"),currency="EUR",evidence_status="manual",
        )
        db.add_all([mortgage,contract]);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,insurance_type="life",annual_premium=Decimal("300"),
            deductible=None,currency="EUR",insured_object_json="{}",
        )
        db.add(policy);db.flush()
        mortgage_id=mortgage.id;policy_id=policy.id

        linked=link_mortgage_insurance(mortgage_id,policy_id,db)
        assert linked["linked"] is True
        relation=db.scalar(select(LinkedProduct).where(
            LinkedProduct.parent_product_type=="mortgage",
            LinkedProduct.parent_product_id==mortgage_id,
            LinkedProduct.linked_product_type=="insurance_policy",
            LinkedProduct.linked_product_id==policy_id,
        ))
        assert relation is not None
        home=wealth_home(mortgage_id,db)
        row=next(item for item in home["insurance"] if item["id"]==policy_id)
        assert row["insurance_type"]=="life"
        assert row["linked_to_mortgage"] is True

        unlinked=unlink_mortgage_insurance(mortgage_id,policy_id,db)
        assert unlinked["linked"] is False
        home=wealth_home(mortgage_id,db)
        assert all(item["id"]!=policy_id for item in home["insurance"])
        db.delete(policy);db.delete(contract);db.delete(mortgage);db.commit()



def test_deleted_insurance_does_not_reappear_from_retained_document():
    with SessionLocal() as db:
        contract=Contract(
            provider_name="Seguro borrable test",contract_type="insurance",
            annual_cost=Decimal("360"),currency="EUR",evidence_status="confirmed",
        )
        db.add(contract);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,insurance_type="home",annual_premium=Decimal("360"),
            currency="EUR",insured_object_json="{}",
        )
        db.add(policy);db.flush()
        document=Document(
            file_path="/tmp/financito-tests/vault/seguro-borrable-test.txt",
            file_name="seguro-borrable-test.txt",mime_type="text/plain",
            sha256="delete-insurance-test-"+policy.id,document_type="insurance",
            status="indexed",page_count=1,extracted_text="Póliza hogar 360 euros",
        )
        db.add(document);db.flush()
        db.add_all([
            ExtractedFact(
                document_id=document.id,fact_type="contract_term",key="annual_cost",
                value_json='{"value":"360","unit":"EUR/year"}',confidence=Decimal("1"),
                status="confirmed",source_page=1,source_section="test",user_verified=True,
            ),
            ExtractedFact(
                document_id=document.id,fact_type="contract_term",key="insurance_type",
                value_json='{"value":"home"}',confidence=Decimal("1"),
                status="confirmed",source_page=1,source_section="test",user_verified=True,
            ),
            EntityLink(
                from_type="document",from_id=document.id,relation_type="evidence_for",
                to_type="insurance_policy",to_id=policy.id,confidence=Decimal("1"),
                source_type="document_projection",source_ref=document.id,
            ),
            EntityLink(
                from_type="document",from_id=document.id,relation_type="evidence_for",
                to_type="contract",to_id=contract.id,confidence=Decimal("1"),
                source_type="document_projection",source_ref=document.id,
            ),
        ])
        db.commit()
        policy_id=policy.id;document_id=document.id

        result=delete_insurance(policy_id,db)
        assert result["deleted"] is True
        assert result["documents_retained"]==1
        retained=db.get(Document,document_id)
        assert retained is not None
        assert retained.document_type=="unknown"
        facts=db.scalars(select(ExtractedFact).where(ExtractedFact.document_id==document_id)).all()
        assert facts
        assert all(f.status=="superseded" for f in facts)

        synchronize_all_document_evidence(db)
        db.flush()
        assert db.get(InsurancePolicy,policy_id) is None
        assert db.scalar(select(InsurancePolicy.id).where(InsurancePolicy.insurance_type=="home",InsurancePolicy.annual_premium==Decimal("360"))) is None

        db.delete(retained)
        db.commit()



def test_insurance_payment_can_be_linked_shown_and_unlinked():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        account=Account(
            name=f"Cuenta seguro {suffix}",institution_name="Banco prueba",
            account_type="checking",currency="EUR",
        )
        contract=Contract(
            provider_name=f"Aseguradora pagos {suffix}",contract_type="insurance",
            annual_cost=Decimal("120"),currency="EUR",evidence_status="manual",
        )
        db.add_all([account,contract]);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,insurance_type="home",annual_premium=Decimal("120"),
            currency="EUR",insured_object_json="{}",
        )
        db.add(policy);db.flush()
        tx=Transaction(
            account_id=account.id,booking_date=date.today(),amount=Decimal("-120"),
            currency="EUR",base_amount=Decimal("-120"),base_currency="EUR",
            description_raw=f"RECIBO SEGURO {suffix}",description_normalized=f"recibo seguro {suffix}",
            merchant_raw=f"Aseguradora pagos {suffix}",merchant_normalized=f"aseguradora pagos {suffix}",
            category_id=None,categorization_method="manual",categorization_confidence=Decimal("1"),
            user_verified=True,is_internal_transfer=False,is_recurring=False,is_extraordinary=False,
            duplicate_fingerprint=uuid4().hex,source="test",
        )
        db.add(tx);db.flush()
        policy_id=policy.id;tx_id=tx.id;account_id=account.id;contract_id=contract.id

        linked=link_transaction_insurance(tx_id,policy_id,db)
        assert linked["linked"] is True

        page=transaction_page(
            q=f"RECIBO SEGURO {suffix}",category_id=None,start=None,end=None,
            page=1,page_size=50,db=db,
        )
        item=next(row for row in page["items"] if row["id"]==tx_id)
        assert item["linked_insurance_policy_id"]==policy_id

        verdict=insurance_verdict(db,use_ai=False)
        policy_row=next(row for row in verdict["policies"] if row["id"]==policy_id)
        assert policy_row["linked_payment_count"]==1
        assert Decimal(policy_row["linked_payments_last_365_total"])==Decimal("120.00")
        payment=policy_row["linked_payments"][0]
        assert payment["transaction_id"]==tx_id
        assert Decimal(payment["amount"])==Decimal("120.00")
        assert payment["account_name"]==f"Cuenta seguro {suffix}"
        assert payment["institution_name"]=="Banco prueba"

        unlinked=unlink_transaction_insurance(tx_id,db)
        assert unlinked["linked"] is False
        verdict=insurance_verdict(db,use_ai=False)
        policy_row=next(row for row in verdict["policies"] if row["id"]==policy_id)
        assert policy_row["linked_payment_count"]==0

        db.delete(tx);db.delete(policy);db.delete(contract);db.delete(account);db.commit()
