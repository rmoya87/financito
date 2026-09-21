from datetime import date
from decimal import Decimal

from sqlalchemy import delete,select

from financito.db import SessionLocal
from financito.models import Contract
from financito.models_analytics import EntitySnapshot
from financito.models_extended import Asset,CoverageFact,InsurancePolicy,Liability
from financito.routes_extended import delete_liability,wealth_details
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
        assert row["previous_value"]=="30000.0000"
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

        db.delete(coverage);db.delete(policy);db.delete(contract);db.commit()
