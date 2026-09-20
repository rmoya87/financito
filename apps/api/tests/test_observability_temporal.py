from datetime import date,timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from financito.db import SessionLocal
from financito.main import app
from financito.models import Account,Transaction
from financito.models_extended import Asset,Liability
from financito.services.temporal import wealth_as_of


def _tx(account_id:str,day:date,amount:str,fingerprint:str)->Transaction:
    return Transaction(
        account_id=account_id,booking_date=day,amount=Decimal(amount),base_amount=Decimal(amount),
        currency="EUR",base_currency="EUR",description_raw=fingerprint,description_normalized=fingerprint,
        duplicate_fingerprint=fingerprint,
    )


def test_as_of_reconstructs_account_and_marks_unknown_components():
    suffix=uuid4().hex[:8]
    today=date.today();past=today-timedelta(days=1)
    with SessionLocal() as db:
        account=Account(name=f"Temporal {suffix}",current_balance=Decimal("1000"))
        db.add(account);db.flush()
        db.add(_tx(account.id,today,"100",f"later-{suffix}"))
        db.add(Asset(asset_type="property",name=f"Future valuation {suffix}",currency="EUR",current_value=Decimal("5000"),valuation_date=today,valuation_source="manual",ownership_percentage=Decimal("100")))
        liability=Liability(liability_type="loan",name=f"Historical unknown {suffix}",outstanding_amount=Decimal("3000"),currency="EUR",ownership_percentage=Decimal("100"))
        db.add(liability);db.flush()
        result=wealth_as_of(db,past)
        row=next(x for x in result["accounts"] if x["id"]==account.id)
        assert Decimal(row["balance"])==Decimal("900.00")
        assert row["method"]=="current_balance_minus_later_transactions"
        assert any(x["name"]==f"Future valuation {suffix}" for x in result["unknown"]["assets"])
        assert result["unknown"]["historical_debt"] is True
        assert any(x["id"]==liability.id for x in result["unknown"]["debt"])
        assert result["status"]=="partial"


def test_developer_snapshot_and_temporal_api_do_not_leak_secrets():
    with TestClient(app) as client:
        session=client.get("/api/v1/session");assert session.status_code==200
        csrf=session.json()["csrf_token"]
        snap=client.get("/api/v1/developer/snapshot")
        assert snap.status_code==200
        data=snap.json()
        assert data["runtime"]["local_only"] is True
        assert data["schema_version"]>=5
        serialized=str(data["providers"]).lower()
        assert "begin private key" not in serialized
        future=(date.today()+timedelta(days=1)).isoformat()
        response=client.get("/api/v1/temporal/wealth?as_of="+future)
        assert response.status_code==400
