from decimal import Decimal
import json
from uuid import uuid4

from financito.db import SessionLocal
from financito.models import Contract,Document,ExtractedFact,Mortgage
from financito.models_analytics import EntityLink,LinkedProduct
from financito.models_extended import InsurancePolicy
from financito.services.contractual_costs import (
    linked_product_rate_impacts,
    prepayment_restrictions,
    resolve_prepayment_penalty,
    resolve_subrogation_penalty,
    switching_readiness,
)


def _mortgage(db):
    row=Mortgage(
        lender="Bankinter test",
        remaining_principal=Decimal("100000"),
        currency="EUR",
        interest_type="fixed",
        nominal_rate=Decimal("0.025"),
        monthly_payment=Decimal("600"),
        remaining_months=180,
        early_repayment_fee=None,
    )
    db.add(row);db.flush();return row


def _mortgage_doc(db, mortgage, facts):
    suffix=uuid4().hex
    doc=Document(
        file_path=f"/tmp/{suffix}.pdf",
        file_name=f"hipoteca-{suffix}.pdf",
        mime_type="application/pdf",
        sha256=(suffix*2)[:64],
        document_type="mortgage",
        status="indexed",
        page_count=20,
        extracted_text="test",
    )
    db.add(doc);db.flush()
    db.add(EntityLink(
        from_type="document",
        from_id=doc.id,
        relation_type="evidence_for",
        to_type="mortgage",
        to_id=mortgage.id,
        confidence=Decimal("1"),
        source_type="test",
        source_ref=doc.id,
    ))
    for key,value in facts.items():
        db.add(ExtractedFact(
            document_id=doc.id,
            fact_type="mortgage_term",
            key=key,
            value_json=json.dumps({"value":value,"unit":"percent"}),
            confidence=Decimal("0.99"),
            status="confirmed",
            source_page=7,
            source_section="cláusula confirmada",
            user_verified=True,
        ))
    db.flush();return doc


def test_prepayment_percentage_uses_actual_extra_payment():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        _mortgage_doc(db,mortgage,{"early_repayment_fee_percent":"0.25"})
        result=resolve_prepayment_penalty(db,mortgage,Decimal("12000"))
        assert result["status"]=="confirmed_formula"
        assert result["amount"]==Decimal("30.00")
        assert "0.25%" in result["formula"]
        assert result["source"]["page"]==7


def test_subrogation_percentage_uses_current_remaining_principal():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        _mortgage_doc(db,mortgage,{"subrogation_fee_percent":"0.50"})
        result=resolve_subrogation_penalty(db,mortgage)
        assert result["status"]=="confirmed_formula"
        assert result["amount"]==Decimal("500.00")
        assert result["fact_key"]=="subrogation_fee_percent"


def test_switching_readiness_does_not_invent_unknown_exit_cost():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        result=switching_readiness(db,mortgage.id)
        assert result["ready"] is False
        assert "mortgage_exit_or_subrogation_penalty" in result["missing"]
        assert result["mortgage"]["subrogation_penalty"]["amount"] is None


def test_public_market_parser_only_extracts_explicit_claims_and_rates():
    from financito.services.market_research import _claims,_promo_percent,_rates

    sample=(
        "Hipoteca fija 2,96% TIN y 3,65% TAE. Sin comisión de apertura. "
        "Pagarás un 40% menos en tu Seguro de Hogar. Estudio personalizado."
    )
    rates=_rates(sample)
    assert {"type":"TIN","value_percent":"2.96"} in rates
    assert {"type":"TAE","value_percent":"3.65"} in rates
    claims=_claims(sample)
    assert "no_opening_fee" in claims
    assert "linked_home_insurance" in claims
    assert "personalized_quote" in claims
    assert _promo_percent(sample)=="40"



def test_extracts_and_prices_loss_of_home_insurance_bonus():
    from financito.services.documents import extract_contract_facts

    text=(
        "Si no renuevas el Seguro de Hogar comercializado por el banco "
        "se añade al interés nominal anual bonificado un margen adicional de 0,10 %."
    )
    extracted=extract_contract_facts(text,4)
    match=next(x for x in extracted if x["key"]=="linked_home_insurance_rate_penalty_pp")
    assert match["value"]=="0.10"
    assert match["unit"]=="percentage_points"

    with SessionLocal() as db:
        mortgage=_mortgage(db)
        _mortgage_doc(db,mortgage,{"linked_home_insurance_rate_penalty_pp":"0.10"})
        impacts=linked_product_rate_impacts(db,mortgage)
        home=next(x for x in impacts if x["product"]=="home_insurance")
        assert Decimal(home["monthly_payment_increase"])>Decimal("0")
        assert Decimal(home["remaining_interest_increase"])>Decimal("0")
        assert home["assumption"]=="fixed_rate_contract"



def test_switching_readiness_requires_mapping_when_contract_says_life_insurance_is_linked():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        _mortgage_doc(db,mortgage,{
            "subrogation_fee_percent":"0.50",
            "linked_life_insurance":"mentioned",
        })
        before=switching_readiness(db,mortgage.id)
        assert "linked_insurance_mapping:life" in before["missing"]

        contract=Contract(
            provider_name="Vida hipoteca test",contract_type="insurance",
            annual_cost=Decimal("240"),currency="EUR",evidence_status="confirmed",
            cancellation_notice_days=30,early_exit_penalty=Decimal("0"),
        )
        db.add(contract);db.flush()
        policy=InsurancePolicy(
            contract_id=contract.id,insurance_type="life",annual_premium=Decimal("240"),
            currency="EUR",insured_object_json="{}",
        )
        db.add(policy);db.flush()
        db.add(LinkedProduct(
            parent_product_type="mortgage",parent_product_id=mortgage.id,
            linked_product_type="insurance_policy",linked_product_id=policy.id,
            discount_value=Decimal("0"),discount_unit="manual_link",conditions="test",
        ))
        db.flush()
        after=switching_readiness(db,mortgage.id)
        assert "linked_insurance_mapping:life" not in after["missing"]
        linked=next(x for x in after["insurance"] if x["policy_id"]==policy.id)
        assert linked["linked_to_mortgage"] is True


def test_prepayment_restrictions_enforce_confirmed_permission_and_amount_limits():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        _mortgage_doc(db,mortgage,{
            "partial_prepayment_allowed":"true",
            "prepayment_reduction_options":"both",
            "prepayment_min_amount":"1000",
            "prepayment_max_amount":"10000",
            "prepayment_notice_days":"15",
        })
        ready=prepayment_restrictions(db,mortgage,Decimal("5000"))
        assert ready["calculation_ready"] is True
        assert ready["partial_prepayment_allowed"] is True
        assert ready["effective_min_amount"]=="1000.00"
        assert ready["effective_max_amount"]=="10000.00"
        assert ready["allowed_reduction_options"]==["payment","term"]
        assert ready["notice_days"]==15

        below=prepayment_restrictions(db,mortgage,Decimal("500"))
        assert below["calculation_ready"] is False
        assert any(row["code"]=="below_contract_minimum" for row in below["blockers"])

        above=prepayment_restrictions(db,mortgage,Decimal("12000"))
        assert above["calculation_ready"] is False
        assert any(row["code"]=="above_contract_maximum" for row in above["blockers"])


def test_prepayment_restrictions_do_not_assume_permission_or_ignore_pending_terms():
    with SessionLocal() as db:
        mortgage=_mortgage(db)
        unknown=prepayment_restrictions(db,mortgage,Decimal("5000"))
        assert unknown["calculation_ready"] is False
        assert "partial_prepayment_allowed" in unknown["missing"]

        doc=_mortgage_doc(db,mortgage,{
            "partial_prepayment_allowed":"true",
            "prepayment_reduction_options":"both",
        })
        db.add(ExtractedFact(
            document_id=doc.id,
            fact_type="mortgage_term",
            key="prepayment_max_amount",
            value_json=json.dumps({"value":"6000","unit":"EUR","source":"local_ai_proposal"}),
            confidence=Decimal("0.80"),
            status="inferred",
            source_page=8,
            source_section="IA local: pendiente",
            user_verified=False,
        ))
        db.flush()
        pending=prepayment_restrictions(db,mortgage,Decimal("5000"))
        assert pending["calculation_ready"] is False
        assert [row["key"] for row in pending["pending_review"]]==["prepayment_max_amount"]


def test_deterministic_extractor_finds_explicit_prepayment_operational_terms():
    from financito.services.documents import extract_contract_facts

    text=(
        "El prestatario podrá realizar amortización anticipada parcial. "
        "El importe mínimo será de 1.000 euros y el importe máximo de 20.000 euros. "
        "La amortización anticipada deberá comunicarse con un preaviso de 15 días. "
        "La amortización anticipada se aplicará a reducir cuota o plazo."
    )
    facts=extract_contract_facts(text,3)
    by_key={row["key"]:row for row in facts}
    assert by_key["partial_prepayment_allowed"]["value"]=="true"
    assert by_key["prepayment_min_amount"]["value"]=="1000"
    assert by_key["prepayment_max_amount"]["value"]=="20000"
    assert by_key["prepayment_notice_days"]["value"]=="15"
    assert by_key["prepayment_reduction_options"]["value"]=="both"
