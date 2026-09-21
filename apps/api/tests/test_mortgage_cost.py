from decimal import Decimal

from financito.db import SessionLocal
from financito.models import Mortgage
from financito.models_analytics import LinkedProduct
from financito.models_extended import InsurancePolicy
from financito.services.mortgage_cost import current_remaining_apr_estimate


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

        db.delete(db.scalar(
            __import__("sqlalchemy").select(LinkedProduct).where(LinkedProduct.parent_product_id==mortgage.id)
        ))
        db.flush()
        without_cost=current_remaining_apr_estimate(db,mortgage)
        assert Decimal(without_cost["known_linked_annual_cost"])==Decimal("0.00")
        assert Decimal(without_cost["rate"])<Decimal(with_cost["rate"])

        db.delete(policy);db.delete(mortgage);db.commit()
