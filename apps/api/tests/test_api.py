from fastapi.testclient import TestClient
from financito.main import app

def test_session_health_and_account():
    with TestClient(app) as client:
        session=client.get("/api/v1/session"); assert session.status_code==200
        csrf=session.json()["csrf_token"]; headers={"X-CSRF-Token":csrf}
        created=client.post("/api/v1/accounts",json={"name":"Cuenta","current_balance":"1000"},headers=headers)
        assert created.status_code==200 and created.json()["name"]=="Cuenta"
        health=client.get("/api/v1/health"); assert health.status_code==200 and health.json()["local_only"] is True
