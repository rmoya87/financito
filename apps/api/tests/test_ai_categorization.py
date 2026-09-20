from datetime import date
from decimal import Decimal

from financito.db import SessionLocal
from financito.models import Account,Transaction
from financito.services import local_ai
from financito.services.ai_categorization import improve_categorization
from financito.services.categorization import categorize_transaction,ensure_categories,normalize_text,propagate_verified_merchant


def _tx(account_id:str,desc:str,merchant:str,amount:str,fp:str)->Transaction:
    return Transaction(
        account_id=account_id,booking_date=date(2026,9,20),
        amount=Decimal(amount),base_amount=Decimal(amount),currency="EUR",base_currency="EUR",
        description_raw=desc,description_normalized=normalize_text(desc),
        merchant_raw=merchant,merchant_normalized=normalize_text(merchant),
        duplicate_fingerprint=fp,
    )


def test_verified_merchant_is_learned_and_propagated():
    with SessionLocal() as db:
        cats=ensure_categories(db)
        account=Account(name="AI memory");db.add(account);db.flush()
        verified=_tx(account.id,"Compra habitual","CAFETERIA ACME","-3.50","ai-memory-1")
        verified.category_id=cats["restaurants"].id;verified.user_verified=True;verified.categorization_confidence=Decimal("1")
        pending=_tx(account.id,"Pago tarjeta","CAFETERIA ACME","-4.20","ai-memory-2")
        db.add_all([verified,pending]);db.flush()
        categorize_transaction(db,pending)
        assert pending.category_id==cats["restaurants"].id
        assert pending.categorization_method=="learned_merchant"
        assert pending.categorization_confidence==Decimal("0.98")
        newer=_tx(account.id,"Otro pago","CAFETERIA ACME","-5.00","ai-memory-3")
        db.add(newer);db.flush()
        assert propagate_verified_merchant(db,verified)==1
        assert newer.category_id==cats["restaurants"].id


def test_local_llm_only_handles_unresolved_and_never_marks_verified(monkeypatch):
    with SessionLocal() as db:
        cats=ensure_categories(db)
        account=Account(name="AI local");db.add(account);db.flush()
        target=_tx(account.id,"HIPER LOCAL LAS ROZAS","HIPER LOCAL","-42.10","ai-local-1")
        db.add(target);db.flush();categorize_transaction(db,target)
        assert target.categorization_confidence<Decimal("0.70")
        monkeypatch.setattr(local_ai,"status",lambda:{"available":True,"configured_model":"qwen3:8b","embedding_model":"embeddinggemma","models":["qwen3:8b"],"chat_ready":True,"embedding_ready":False})
        monkeypatch.setattr(local_ai,"generate_json",lambda prompt,timeout=240:{"items":[{"id":target.id,"category":"groceries","confidence":0.91,"reason":"supermercado"}]})
        result=improve_categorization(db,limit=100,llm_limit=10)
        assert result["llm"]==1
        assert target.category_id==cats["groceries"].id
        assert target.categorization_method=="ai_llm"
        assert target.user_verified is False
        assert target.categorization_confidence<=Decimal("0.86")


def test_hybrid_categorizer_does_not_override_user_verified(monkeypatch):
    with SessionLocal() as db:
        cats=ensure_categories(db)
        account=Account(name="AI verified");db.add(account);db.flush()
        tx=_tx(account.id,"Concepto raro","Raro","-10","ai-verified-1")
        tx.category_id=cats["health"].id;tx.user_verified=True;tx.categorization_method="manual";tx.categorization_confidence=Decimal("1")
        db.add(tx);db.flush()
        monkeypatch.setattr(local_ai,"status",lambda:{"available":True,"configured_model":"qwen3:8b","embedding_model":None,"models":["qwen3:8b"],"chat_ready":True,"embedding_ready":False})
        monkeypatch.setattr(local_ai,"generate_json",lambda *a,**k:{"items":[{"id":tx.id,"category":"shopping","confidence":1}]})
        result=improve_categorization(db,limit=100,llm_limit=10)
        assert result["considered"]==0
        assert tx.category_id==cats["health"].id
        assert tx.user_verified is True
