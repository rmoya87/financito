from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete,select

from financito.db import SessionLocal
from financito.domain.analytics import detect_anomalies,detect_recurring
from financito.main import delete_account,update_account
from financito.models import Account,Category,Transaction
from financito.models_analytics import Anomaly,RecurringSeries
from financito.routes_analytics import anomalies as route_anomalies,recurring as route_recurring
from financito.schemas import AccountUpdate
from financito.services.calendar import events
from financito.services.financial_analytics import overview as analytics_overview
from financito.services.snapshots import record_snapshot
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



def test_analysis_keeps_recurring_global_but_filters_anomalies_by_period():
    merchant="period-filter-recurring-test"
    with SessionLocal() as db:
        categories=ensure_categories(db)
        account=Account(name="Period filter test",current_balance=Decimal("1000"),source="manual")
        anomaly_category=Category(name="Period filter anomaly",system_key="period_filter_anomaly_"+uuid4().hex)
        db.add_all([account,anomaly_category]);db.flush()

        for when in (date(2026,6,2),date(2026,7,2),date(2026,8,2)):
            _tx(db,account.id,when,"-20","Suscripción "+when.isoformat(),merchant,categories["subscriptions"].id)

        for when,amount in (
            (date(2026,8,1),"-10"),
            (date(2026,8,5),"-10"),
            (date(2026,8,10),"-10"),
            (date(2026,8,15),"-10"),
            (date(2026,9,3),"-100"),
        ):
            _tx(db,account.id,when,amount,"Compra patrón "+when.isoformat(),"outlier-period-test",anomaly_category.id)
        db.flush()
        detect_recurring(db,use_ai=False)
        detect_anomalies(db)
        db.commit()

        recurring_rows=route_recurring(db)
        assert any(item["merchant"]==merchant for item in recurring_rows)

        anomalies_august=route_anomalies(date(2026,8,1),date(2026,8,31),db)
        anomalies_september=route_anomalies(date(2026,9,1),date(2026,9,30),db)
        assert not any(item["transaction"] and item["transaction"]["merchant"]=="outlier-period-test" for item in anomalies_august)
        assert any(item["transaction"] and item["transaction"]["merchant"]=="outlier-period-test" for item in anomalies_september)

        db.execute(delete(Anomaly).where(Anomaly.transaction_id.in_(
            select(Transaction.id).where(Transaction.account_id==account.id)
        )))
        db.execute(delete(RecurringSeries).where(RecurringSeries.merchant_normalized==merchant))
        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account)
        db.delete(anomaly_category)
        db.commit()



def test_daily_overview_fills_each_day_of_selected_month_range():
    with SessionLocal() as db:
        account=Account(name="Daily analytics test",current_balance=Decimal("1000"),source="manual")
        db.add(account);db.flush()
        _tx(db,account.id,date(2040,2,1),"1200","Nómina diaria test","empresa daily test")
        _tx(db,account.id,date(2040,2,3),"-40","Compra diaria test","tienda daily test")
        db.commit()

        data=analytics_overview(db,date(2040,2,1),date(2040,2,4))
        assert [row["period"] for row in data["daily"]]==[
            "2040-02-01","2040-02-02","2040-02-03","2040-02-04"
        ]
        assert data["daily"][0]["income"]=="1200.00"
        assert data["daily"][1]["income"]=="0.00"
        assert data["daily"][2]["expenses"]=="40.00"
        assert Decimal(data["merchant_spending_total"])==Decimal("40.00")

        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account);db.commit()


def test_account_delete_removes_only_selected_account_and_transactions():
    with SessionLocal() as db:
        doomed=Account(name="Delete me",current_balance=Decimal("100"),source="manual")
        survivor=Account(name="Keep me",current_balance=Decimal("200"),source="manual")
        db.add_all([doomed,survivor]);db.flush()
        _tx(db,doomed.id,date(2026,9,1),"-10","Delete tx","delete merchant")
        _tx(db,survivor.id,date(2026,9,1),"-20","Keep tx","keep merchant")
        record_snapshot(db,"account",doomed.id,{"balance":"100","currency":"EUR"},date(2026,9,1),"test")
        db.commit()

        doomed_id=doomed.id
        survivor_id=survivor.id
        result=delete_account(doomed_id,db)
        assert result["deleted"]==doomed_id
        assert result["transactions_deleted"]==1
        assert db.scalar(select(Account.id).where(Account.id==doomed_id)) is None
        assert db.scalar(select(Account.id).where(Account.id==survivor_id))==survivor_id
        assert db.scalar(select(Transaction.id).where(Transaction.account_id==doomed_id)) is None
        assert db.scalar(select(Transaction.id).where(Transaction.account_id==survivor_id)) is not None
        from financito.models_analytics import EntitySnapshot
        assert db.scalar(select(EntitySnapshot.id).where(EntitySnapshot.entity_type=="account",EntitySnapshot.entity_id==doomed_id)) is None

        db.execute(delete(Transaction).where(Transaction.account_id==survivor.id))
        db.delete(survivor);db.commit()
