import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Document,ExtractedFact,Mortgage
from financito.models_analytics import EntityLink,LinkedProduct
from financito.models_extended import CoverageFact,InsurancePolicy,MortgageProfileExtra
from financito.routes_extended import wealth_home
from financito.services.evidence import synchronize_document_evidence
from financito.services.insurance_analysis import insurance_verdict


def _fact(
    document_id:str,
    fact_type:str,
    key:str,
    value,
    *,
    page:int=1,
    unit:str|None=None,
    extra:dict|None=None,
):
    payload={"value":value,"source":"local_ai_proposal"}
    if unit is not None:
        payload["unit"]=unit
    if extra:
        payload.update(extra)
    return ExtractedFact(
        document_id=document_id,
        fact_type=fact_type,
        key=key,
        value_json=json.dumps(payload,ensure_ascii=False),
        confidence=Decimal("0.85"),
        status="confirmed",
        source_page=page,
        source_section="Confirmado por el usuario",
        user_verified=True,
    )


def test_confirmed_embedded_life_insurance_projects_to_mortgage_and_insurance():
    with SessionLocal() as db:
        try:
            mortgage=Mortgage(
                lender="Bankinter",
                remaining_principal=Decimal("150000"),
                currency="EUR",
                interest_type="fixed",
                nominal_rate=Decimal("0.025"),
                monthly_payment=Decimal("800"),
                remaining_months=240,
                early_repayment_fee=None,
            )
            db.add(mortgage);db.flush()

            document=Document(
                file_path="/tmp/financito-test-mixed-mortgage.pdf",
                file_name="hipoteca-bankinter-con-seguro-vida.pdf",
                mime_type="application/pdf",
                sha256="f"*64,
                document_type="mortgage",
                status="indexed",
                page_count=2,
                extracted_text="Hipoteca y seguro de vida vinculado",
            )
            db.add(document);db.flush()
            db.add(EntityLink(
                from_type="document",
                from_id=document.id,
                relation_type="evidence_for",
                to_type="mortgage",
                to_id=mortgage.id,
                confidence=Decimal("1"),
                source_type="user",
                source_ref=document.id,
            ))

            # Mortgage data remains mortgage data.
            db.add(_fact(document.id,"mortgage_term","remaining_principal","149000",page=2))

            # The same PDF contains a confirmed linked life policy on page 1.
            facts=[
                _fact(document.id,"linked_product","linked_life_insurance","mentioned",unit="boolean_signal"),
                _fact(document.id,"contract_term","renewal_date","26/05/2027"),
                _fact(document.id,"contract_term","insurance_type","Vida Anual Renovable"),
                _fact(document.id,"contract_term","insured_object","Fallecimiento por cualquier causa e Invalidez absoluta y permanente"),
                _fact(document.id,"contract_term","annual_cost","378.62",unit="EUR"),
                _fact(document.id,"contract_term","contract_number","0128 0064 36 0510018972"),
                _fact(document.id,"contract_term","provider_name","Bankinter Seguros De Vida S.a."),
                _fact(document.id,"contract_term","next_review_date","2027-05-26"),
                _fact(
                    document.id,"coverage_fact","coverage:fallecimiento_por_cualquier_causa:1:0",
                    "Fallecimiento por cualquier causa",
                    extra={"coverage_type":"Fallecimiento por cualquier causa","limit_amount":"118000"},
                ),
                _fact(
                    document.id,"coverage_fact","coverage:invalidez_absoluta_y_permanente:1:1",
                    "Invalidez absoluta y permanente",
                    extra={"coverage_type":"Invalidez absoluta y permanente","limit_amount":"118000"},
                ),
            ]
            db.add_all(facts);db.flush()

            sync=synchronize_document_evidence(db,document)
            db.flush()

            assert sync["mortgage_id"]==mortgage.id
            assert sync["insurance_policy_id"] is not None
            assert sync["coverage_count"]==2

            # Insurance provider/date must never overwrite the mortgage lender
            # or a mortgage rate-review date merely because they share a PDF.
            db.refresh(mortgage)
            assert mortgage.lender=="Bankinter"
            assert mortgage.remaining_principal==Decimal("149000")
            extra=db.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage.id))
            assert extra is None or extra.next_review_date is None

            policy=db.get(InsurancePolicy,sync["insurance_policy_id"])
            assert policy is not None
            assert policy.insurance_type=="life"
            assert policy.annual_premium==Decimal("378.62")
            assert policy.policy_number_masked=="0128 0064 36 0510018972"
            assert "Fallecimiento por cualquier causa" in policy.insured_object_json

            insurance_contract=policy.contract_id and db.get(__import__("financito.models",fromlist=["Contract"]).Contract,policy.contract_id)
            assert insurance_contract is not None
            assert insurance_contract.provider_name=="Bankinter Seguros De Vida S.a."
            assert insurance_contract.renewal_date==date(2027,5,26)
            assert insurance_contract.annual_cost==Decimal("378.62")

            coverages=db.scalars(select(CoverageFact).where(
                CoverageFact.insurance_policy_id==policy.id,
                CoverageFact.source_document_id==document.id,
            )).all()
            assert {row.coverage_type for row in coverages}=={
                "Fallecimiento por cualquier causa",
                "Invalidez absoluta y permanente",
            }
            assert {row.limit_amount for row in coverages}=={Decimal("118000")}

            relation=db.scalar(select(LinkedProduct).where(
                LinkedProduct.parent_product_type=="mortgage",
                LinkedProduct.parent_product_id==mortgage.id,
                LinkedProduct.linked_product_type=="insurance_policy",
                LinkedProduct.linked_product_id==policy.id,
            ))
            assert relation is not None

            home=wealth_home(mortgage.id,db)
            linked=next(row for row in home["insurance"] if row["id"]==policy.id)
            assert linked["linked_to_mortgage"] is True
            assert linked["provider"]=="Bankinter Seguros De Vida S.a."

            verdict=insurance_verdict(db,use_ai=False)
            verdict_policy=next(row for row in verdict["policies"] if row["id"]==policy.id)
            assert verdict_policy["annual_premium"]=="378.6200"
            assert len(verdict_policy["coverages"])==2
        finally:
            db.rollback()
