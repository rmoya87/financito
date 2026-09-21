from datetime import date
from decimal import Decimal

from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Mortgage
from financito.models_analytics import LinkedProduct
from financito.models_extended import InsurancePolicy
from financito.services import mortgage_cost
from financito.services.mortgage_cost import current_remaining_apr_estimate,due_rate_review_estimate


def test_current_remaining_apr_estimate_tracks_tin_and_known_linked_costs():
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender="TAE estimate test",
            remaining_principal=Decimal("100000"),
            currency="EUR",
            interest_type="fixed",
            nominal_rate=Decimal("0.03"),
            monthly_payment=Decimal("690"),
            remaining_months=180,
        )
        policy=InsurancePolicy(
            insurance_type="home",
            annual_premium=Decimal("600"),
            currency="EUR",
            insured_object_json="{}",
        )
        db.add_all([mortgage,policy]);db.flush()
        db.add(LinkedProduct(
            parent_product_type="mortgage",
            parent_product_id=mortgage.id,
            linked_product_type="insurance_policy",
            linked_product_id=policy.id,
            discount_value=Decimal("0"),
            discount_unit="currency",
            conditions="test",
        ))
        db.commit()

        with_cost=current_remaining_apr_estimate(db,mortgage)
        assert with_cost["status"]=="estimated"
        assert Decimal(with_cost["known_linked_annual_cost"])==Decimal("600.00")
        assert Decimal(with_cost["rate"])>Decimal("0.03")

        db.delete(db.scalar(select(LinkedProduct).where(LinkedProduct.parent_product_id==mortgage.id)))
        db.flush()
        without_cost=current_remaining_apr_estimate(db,mortgage)
        assert Decimal(without_cost["known_linked_annual_cost"])==Decimal("0.00")
        assert Decimal(without_cost["rate"])<Decimal(with_cost["rate"])

        db.delete(policy);db.delete(mortgage);db.commit()


class _FakeEcb:
    def series(self,flow,key,start=None,end=None,last_n=None):
        assert flow=="FM"
        assert key=="M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"
        assert start=="2026-07"
        assert end=="2026-07"
        return [{"TIME_PERIOD":"2026-07","OBS_VALUE":"2.5000"}]


def test_due_rate_review_uses_exact_confirmed_month_rule_without_mutating_saved_rate(monkeypatch):
    with SessionLocal() as db:
        mortgage=Mortgage(
            lender="Variable review test",
            remaining_principal=Decimal("150000"),
            currency="EUR",
            interest_type="variable",
            nominal_rate=Decimal("0.030000"),
            monthly_payment=Decimal("830"),
            remaining_months=240,
        )
        db.add(mortgage);db.commit()
        original_rate=mortgage.nominal_rate
        monkeypatch.setattr(mortgage_cost,"rate_review_readiness",lambda session,row:{
            "status":"ready",
            "automatic":True,
            "missing":[],
            "reference_index":"Euríbor 12 meses",
            "differential_rate":"0.007500",
            "rate_review_months":12,
            "next_review_date":"2026-09-01",
            "reference_index_lag_months":2,
            "rule":"test",
        })

        result=due_rate_review_estimate(db,mortgage,as_of=date(2026,9,21),provider=_FakeEcb())
        assert result["status"]=="estimated_due"
        assert result["estimate"]["reference_month"]=="2026-07"
        assert Decimal(result["estimate"]["estimated_nominal_rate"])==Decimal("0.032500")
        assert Decimal(result["estimate"]["estimated_monthly_payment"])>0
        assert Decimal(result["estimate"]["estimated_current_apr"])>Decimal("0.0325")
        assert mortgage.nominal_rate==original_rate
        assert result["estimate"]["confirmation_required"] is True

        db.delete(mortgage);db.commit()
