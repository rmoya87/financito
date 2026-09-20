from decimal import Decimal
from sqlalchemy import select
from financito.db import SessionLocal
from financito.models import Account, Transaction
from financito.services.imports import import_csv

def test_csv_import_is_idempotent():
    with SessionLocal() as db:
        account=Account(name="Import test",current_balance=Decimal("0")); db.add(account); db.commit(); db.refresh(account)
        content="Fecha;Concepto;Importe\n20/09/2026;Mercadona;-45,90\n".encode()
        first=import_csv(db,account.id,content,"test.csv"); db.commit(); second=import_csv(db,account.id,content,"test.csv"); db.commit()
        assert first.inserted==1 and second.duplicates==1
        rows=db.scalars(select(Transaction).where(Transaction.account_id==account.id)).all(); assert len(rows)==1 and rows[0].amount==Decimal("-45.9000")
