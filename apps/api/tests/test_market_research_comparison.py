from decimal import Decimal

from financito.db import SessionLocal
from financito.domain.engines import MortgageEngine
from financito.models import Mortgage
from financito.services import market_research


def _source_result(source,rate=None,claims=None):
    return {
        **source,
        "status":"ok" if rate is not None else "unavailable",
        "retrieved_at":"2026-09-21T10:00:00+00:00",
        "rates":[] if rate is None else [{"type":"TIN","value_percent":str(rate)}],
        "claims":claims or [],
        "promo_percent":None,
        "requires_personalized_quote":True,
    }


def test_market_scan_only_marks_offers_that_recover_confirmed_penalty(monkeypatch):
    with SessionLocal() as db:
        principal=Decimal("100000")
        rate=Decimal("0.04")
        months=120
        current=MortgageEngine.amortization(principal,rate,months)
        mortgage=Mortgage(
            lender="Current Bank",
            remaining_principal=principal,
            currency="EUR",
            interest_type="fixed",
            nominal_rate=rate,
            monthly_payment=current.monthly_payment,
            remaining_months=months,
            early_repayment_fee=Decimal("1000"),
        )
        db.add(mortgage);db.commit()

        def fake_scan(source,client):
            if source["id"]=="santander_subrogation":
                return _source_result(source,"2.0",["subrogation"])
            if source["id"]=="bbva_subrogation":
                return _source_result(source,"1.8",["subrogation","linked_life_insurance"])
            if source["id"]=="ing_subrogation":
                return _source_result(source,"3.95",["subrogation"])
            return _source_result(source)
        monkeypatch.setattr(market_research,"_scan_source",fake_scan)

        result=market_research.scan_public_market(db,mortgage.id)
        providers=[row["provider"] for row in result["better_offers"]]
        assert providers==["Santander"]
        santander=result["better_offers"][0]
        assert santander["scenario"]["compensates"] is True
        assert Decimal(santander["scenario"]["break_even_months"])<Decimal(months)
        assert Decimal(santander["scenario"]["known_exit_penalty"])==Decimal("1000")
        rejected={row["provider"]:row for row in result["lower_rate_but_not_better"]}
        assert "BBVA" in rejected
        assert "seguro vinculado" in rejected["BBVA"]["scenario"]["rejection_reason"]
        assert "ING" in rejected
        assert result["conclusion"]["provider"]=="Santander"

        db.delete(mortgage);db.commit()


def test_lower_rate_is_not_better_when_penalty_never_recovers(monkeypatch):
    with SessionLocal() as db:
        principal=Decimal("100000")
        rate=Decimal("0.04")
        months=36
        current=MortgageEngine.amortization(principal,rate,months)
        mortgage=Mortgage(
            lender="Penalty Bank",
            remaining_principal=principal,
            currency="EUR",
            interest_type="fixed",
            nominal_rate=rate,
            monthly_payment=current.monthly_payment,
            remaining_months=months,
            early_repayment_fee=Decimal("25000"),
        )
        db.add(mortgage);db.commit()

        monkeypatch.setattr(
            market_research,
            "_scan_source",
            lambda source,client:_source_result(source,"2.0",["subrogation"]) if source["id"]=="santander_subrogation" else _source_result(source),
        )
        result=market_research.scan_public_market(db,mortgage.id)

        assert result["better_offers"]==[]
        assert any(row["provider"]=="Santander" for row in result["lower_rate_but_not_better"])
        row=next(row for row in result["lower_rate_but_not_better"] if row["provider"]=="Santander")
        assert row["scenario"]["compensates"] is False
        assert "no se recupera" in row["scenario"]["rejection_reason"]
        assert "no se ha demostrado que te compense" in result["conclusion"]["headline"].lower()

        db.delete(mortgage);db.commit()
