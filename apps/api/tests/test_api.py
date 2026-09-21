from fastapi.testclient import TestClient
from financito.main import app

def test_session_health_and_account():
    with TestClient(app) as client:
        session=client.get("/api/v1/session"); assert session.status_code==200
        csrf=session.json()["csrf_token"]; headers={"X-CSRF-Token":csrf}
        created=client.post("/api/v1/accounts",json={"name":"Cuenta","current_balance":"1000"},headers=headers)
        assert created.status_code==200 and created.json()["name"]=="Cuenta"
        health=client.get("/api/v1/health"); assert health.status_code==200 and health.json()["local_only"] is True


def test_enable_banking_rejects_plain_http_callback_before_provider_call():
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        response=client.post(
            "/api/v1/banking/auth?bank_name=Demo&country=ES&state=x&valid_until=2026-10-01T00%3A00%3A00Z&redirect_url=http%3A%2F%2F127.0.0.1%3A8765%2Fbanking%2F",
            headers=headers,
        )
        assert response.status_code==400
        assert "HTTPS" in response.json()["detail"]


def test_manual_asset_can_be_updated_and_deleted():
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        assert session.status_code==200
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        payload={
            "asset_type":"vehicle",
            "name":"Coche de prueba",
            "current_value":"15000",
            "currency":"EUR",
            "valuation_date":"2026-09-01",
            "valuation_source":"manual",
            "ownership_type":"personal",
            "ownership_percentage":"100",
        }
        created=client.post("/api/v1/assets",json=payload,headers=headers)
        assert created.status_code==200
        asset_id=created.json()["id"]

        updated=client.patch(
            f"/api/v1/assets/{asset_id}",
            json={**payload,"current_value":"14000","name":"Coche actualizado"},
            headers=headers,
        )
        assert updated.status_code==200

        details=client.get("/api/v1/wealth/details")
        row=next(x for x in details.json()["assets"] if x["id"]==asset_id)
        assert row["name"]=="Coche actualizado"
        assert row["value"]=="14000.0000"

        deleted=client.delete(f"/api/v1/assets/{asset_id}",headers=headers)
        assert deleted.status_code==200
        assert deleted.json()["deleted"] is True
        assert all(x["id"]!=asset_id for x in client.get("/api/v1/wealth/details").json()["assets"])
