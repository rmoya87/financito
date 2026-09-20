from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from financito.config import settings
from financito.db import SessionLocal
from financito.models import Account,Category,Document,ExtractedFact,Transaction
from financito.models_analytics import EntityLink
from financito.services.categorization import ensure_categories
from financito.services.documents import classify_document,detect_language,index_document
from financito.services.financial_analytics import overview
from financito.services.transaction_ops import detect_refunds


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
