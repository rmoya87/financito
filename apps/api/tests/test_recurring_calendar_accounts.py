from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from financito.db import SessionLocal
from financito.domain.analytics import detect_recurring
from financito.main import update_account
from financito.models import Account, Transaction
from financito.models_analytics import RecurringSeries
from financito.schemas import AccountUpdate
from financito.services.calendar import events
from financito.services.categorization import ensure_categories


def _tx(db,account_id,when,amount,label,merchant,category_id=None):
    row=Transaction(
        account_id=account_id,
        booking_date=when,
        amount=Decimal(str(amount)),
        base_amount=Decimal(str(amount)),
        currency="EUR",
        base_currency="EUR",
        description_raw=label,
        description_normalized=label.lower(),
        merchant_raw=merchant,
        merchant_normalized=merchant.lower() if merchant else None,
        category_id=category_id,
        duplicate_fingerprint=str(uuid4()),
    )
    db.add(row)
    return row


def test_recurring_detection_and_90_day_historical_patterns():
    merchant="colegio recurrente test"
    with SessionLocal() as db:
        categories=ensure_categories(db)
        account=Account(name="Pattern test",current_balance=Decimal("5000"),source="manual")
        db.add(account);db.flush()

        for when in (date(2026,6,5),date(2026,7,5),date(2026,8,5)):
            _tx(db,account.id,when,"-315","Cuota colegio "+when.isoformat(),merchant,categories["education"].id)

        grocery_values=[
            (date(2026,5,10),"-480"),
            (date(2026,6,10),"-510"),
            (date(2026,7,10),"-500"),
            (date(2026,8,10),"-520"),
        ]
        for when,amount in grocery_values:
            _tx(db,account.id,when,amount,"Compra alimentación "+when.isoformat(),"supermercado test "+when.isoformat(),categories["groceries"].id)
        db.commit()

        series=detect_recurring(db,use_ai=False)
        db.commit()
        own=next((row for row in series if row.merchant_normalized==merchant),None)
        assert own is not None
        assert own.cadence=="monthly"
        assert own.expected_amount==Decimal("315")

        upcoming=events(db,date(2026,9,21),date(2026,12,20))
        assert any(item["type"]=="recurring" and merchant in item["title"] for item in upcoming)
        grocery=[item for item in upcoming if item["type"]=="historical_pattern" and item.get("category")=="Supermercado"]
        assert len(grocery)>=2
        assert all(Decimal(item["amount"])>Decimal("0") for item in grocery)
        assert all(item.get("basis") for item in grocery)

        db.execute(delete(RecurringSeries).where(RecurringSeries.merchant_normalized==merchant))
        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account);db.commit()


def test_manual_balance_can_be_corrected_but_connected_balance_is_bank_owned():
    with SessionLocal() as db:
        manual=Account(name="Ahorro manual test",current_balance=Decimal("0"),source="manual",sync_status="local")
        connected=Account(name="Banco conectado test",current_balance=Decimal("100"),source="enable_banking",sync_status="synced")
        db.add_all([manual,connected]);db.commit()

        updated=update_account(manual.id,AccountUpdate(current_balance=Decimal("40000")),db)
        assert updated.current_balance==Decimal("40000")

        with pytest.raises(HTTPException) as exc:
            update_account(connected.id,AccountUpdate(current_balance=Decimal("999")),db)
        assert exc.value.status_code==409

        db.delete(manual);db.delete(connected);db.commit()
