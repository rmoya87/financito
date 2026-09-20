from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from financito.config import settings
from financito.db import SessionLocal
from financito.models import Account,ActionItem,Category,Contract,Document,ExtractedFact,Transaction
from financito.models_analytics import EntityLink
from financito.services.categorization import ensure_categories
from financito.services.documents import classify_document,detect_language,index_document,store_uploaded_document
from financito.services.financial_analytics import overview
from financito.services.evidence import structured_evidence_context,synchronize_document_evidence
from financito.services.document_ai import analyze_document,domain_insights,latest_analysis
from financito.services.transaction_ops import detect_refunds
from financito.models_extended import InsurancePolicy


def _tx(account_id:str,day:date,amount:str,desc:str,merchant:str,fp:str):
    return Transaction(
        account_id=account_id,booking_date=day,amount=Decimal(amount),base_amount=Decimal(amount),
        currency="EUR",base_currency="EUR",description_raw=desc,description_normalized=desc.lower(),
        merchant_raw=merchant,merchant_normalized=merchant.lower(),duplicate_fingerprint=fp,
    )


def test_refund_reduces_expense_and_not_income():
    with SessionLocal() as db:
        cats=ensure_categories(db)
        account=Account(name="Refunds");db.add(account);db.flush()
        expense=_tx(account.id,date(2026,9,1),"-50.00","Compra demo","Tienda Demo","refund-expense")
        expense.category_id=cats["shopping"].id;expense.categorization_confidence=Decimal("1")
        refund=_tx(account.id,date(2026,9,5),"50.00","Devolución demo","Tienda Demo","refund-credit")
        db.add_all([expense,refund]);db.flush()
        assert detect_refunds(db)==1
        data=overview(db,date(2026,9,1),date(2026,9,30))
        assert Decimal(data["cash_flow"]["income"])==Decimal("0.00")
        assert Decimal(data["cash_flow"]["expenses"])==Decimal("0.00")
        assert refund.category_id==expense.category_id
        link=db.scalar(select(EntityLink).where(EntityLink.from_id==refund.id,EntityLink.relation_type=="refund_of"))
        assert link is not None


def test_document_classification_language_and_fact_source_page():
    text="Póliza de seguro de hogar. La prima anual será de 240 euros. Franquicia de 150 euros. Preaviso de 30 días para cancelar."
    kind,confidence=classify_document(text,"poliza_hogar.txt")
    language,lang_conf=detect_language(text)
    assert kind=="insurance" and confidence>0.5
    assert language=="es" and lang_conf>0.5
    path=settings.vault_dir/"poliza-hogar-ci.txt"
    path.write_text(text,encoding="utf-8")
    with SessionLocal() as db:
        result=index_document(db,str(path),"unknown");db.commit()
        assert result.document.document_type=="insurance"
        facts=db.scalars(select(ExtractedFact).where(ExtractedFact.document_id==result.document.id,ExtractedFact.fact_type=="contract_term")).all()
        assert {f.key for f in facts}>={"annual_cost","deductible","cancellation_notice_days"}
        assert all(f.source_page==1 for f in facts)
        assert all(f.source_section for f in facts)


def test_mortgage_fein_extracts_structured_terms():
    text=(
        "FEIN préstamo hipotecario a tipo variable. Índice Euríbor a 12 meses más diferencial del 0,75 %. "
        "TIN 3,10 %. TAE 3,45 %. Plazo de 25 años. Revisión cada 12 meses. "
        "Comisión de apertura 0,50 %. Compensación por reembolso anticipado 0,25 %. "
        "Bonificación mediante domiciliación de nómina y seguro de hogar."
    )
    path=settings.vault_dir/"fein-ci.txt"
    path.write_text(text,encoding="utf-8")
    with SessionLocal() as db:
        result=index_document(db,str(path),"unknown");db.commit()
        assert result.document.document_type=="mortgage"
        facts=db.scalars(select(ExtractedFact).where(ExtractedFact.document_id==result.document.id)).all()
        keys={f.key for f in facts}
        assert {"reference_index","interest_type","differential_rate","mortgage_term_years","rate_review_months","opening_fee_percent","early_repayment_fee_percent","linked_salary","linked_home_insurance"} <= keys
        assert all(f.source_page==1 for f in facts if f.key in keys)



def test_confirmed_document_evidence_projects_and_closes_review_action():
    suffix=uuid4().hex[:8]
    text=(
        "Póliza de seguro de hogar. Prima anual de 360 euros. Franquicia de 120 euros. "
        "Preaviso de 30 días. Renovación 30/09/2027."
    )
    path=settings.vault_dir/f"poliza-evidencia-{suffix}.txt"
    path.write_text(text,encoding="utf-8")
    with SessionLocal() as db:
        result=index_document(db,str(path),"unknown")
        db.flush()
        doc=result.document
        assert doc.document_type=="insurance"

        action=db.scalar(select(ActionItem).where(
            ActionItem.action_type=="review_document_evidence",
            ActionItem.related_entity_id==doc.id,
        ))
        assert action is not None
        assert action.status=="pending"

        facts=db.scalars(select(ExtractedFact).where(
            ExtractedFact.document_id==doc.id,
            ExtractedFact.fact_type.in_(["contract_term","mortgage_term","linked_product"]),
        )).all()
        assert facts
        for fact in facts:
            fact.status="confirmed"
            fact.user_verified=True

        sync=synchronize_document_evidence(db,doc)
        db.commit()
        assert sync["pending"]==0

        db.refresh(action)
        assert action.status=="done"

        contract_link=db.scalar(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.from_id==doc.id,
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="contract",
        ))
        assert contract_link is not None
        contract=db.get(Contract,contract_link.to_id)
        assert contract is not None
        assert contract.annual_cost==Decimal("360")
        assert contract.cancellation_notice_days==30
        assert contract.renewal_date==date(2027,9,30)
        assert contract.evidence_status=="confirmed"

        policy_link=db.scalar(select(EntityLink).where(
            EntityLink.from_type=="document",
            EntityLink.from_id==doc.id,
            EntityLink.relation_type=="evidence_for",
            EntityLink.to_type=="insurance_policy",
        ))
        assert policy_link is not None
        policy=db.get(InsurancePolicy,policy_link.to_id)
        assert policy is not None
        assert policy.annual_premium==Decimal("360")
        assert policy.deductible==Decimal("120")

        evidence=structured_evidence_context(db)
        projected=next(x for x in evidence["documents"] if x["document_id"]==doc.id)
        assert any(x["key"]=="annual_cost" and x["user_verified"] for x in projected["facts"])



def test_uploaded_document_is_safely_stored_and_indexed():
    path=store_uploaded_document("../../Hipoteca prueba?.txt",b"FEIN hipoteca. TIN 2,50 %. TAE 2,90 %.")
    assert settings.vault_dir.resolve() in path.resolve().parents
    assert path.parent.name=="uploads"
    assert "?" not in path.name
    with SessionLocal() as db:
        result=index_document(db,str(path),"unknown")
        db.commit()
        assert result.document.document_type=="mortgage"
        assert result.document.file_name==path.name


def test_local_ai_document_analysis_is_persisted_and_shared(monkeypatch):
    suffix=uuid4().hex[:8]
    path=settings.vault_dir/f"seguro-ia-{suffix}.txt"
    path.write_text(
        "Póliza de seguro de hogar. Prima anual 420 euros. Franquicia 150 euros. "
        "Preaviso 30 días. La cobertura incluye responsabilidad civil.",
        encoding="utf-8",
    )
    with SessionLocal() as db:
        indexed=index_document(db,str(path),"unknown")
        document=indexed.document

        monkeypatch.setattr(
            "financito.services.document_ai.ai_status",
            lambda:{"available":True,"configured_model":"qwen3:8b","chat_ready":True},
        )
        monkeypatch.setattr(
            "financito.services.document_ai.generate_json",
            lambda prompt,timeout=180:{
                "summary":"Seguro con prima y franquicia identificadas; conviene contrastar coberturas antes de cambiar.",
                "advantages":[{"title":"Responsabilidad civil","detail":"Figura como cobertura incluida.","pages":[1],"impact":"Cobertura útil a mantener al comparar."}],
                "penalties":[],
                "obligations":[{"title":"Preaviso","detail":"Se ha detectado un preaviso contractual.","pages":[1],"impact":""}],
                "risks":[],
                "exclusions_or_limits":[{"title":"Franquicia","detail":"Existe franquicia.","pages":[1],"impact":"Afecta al coste efectivo de un siniestro."}],
                "linked_products":[],
                "optimization_opportunities":[{"title":"Comparar prima equivalente","detail":"Solicitar ofertas con coberturas equivalentes.","pages":[1],"impact":"No comparar solo por precio."}],
                "cross_area_impacts":[],
                "missing_information":[{"title":"Límites de cobertura","detail":"No aparecen completos en el fragmento.","pages":[],"impact":""}],
                "confidence":0.88,
            },
        )

        result=analyze_document(db,document)
        db.commit()
        assert result["status"]=="ready"
        stored=latest_analysis(db,document.id)
        assert stored is not None
        assert stored["summary"].startswith("Seguro con prima")
        assert stored["optimization_opportunities"][0]["title"]=="Comparar prima equivalente"

        insights=domain_insights(db,"insurance")
        assert any(x["document_id"]==document.id for x in insights)

        evidence=structured_evidence_context(db)
        projected=next(x for x in evidence["documents"] if x["document_id"]==document.id)
        assert projected["ai_analysis"]["summary"].startswith("Seguro con prima")
        assert "interpretación" in evidence["rule"].lower()
