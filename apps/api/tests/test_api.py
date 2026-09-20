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
