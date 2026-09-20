from datetime import date

from fastapi.testclient import TestClient

from financito.main import app
from financito.providers.market import StooqProvider


def _client_and_headers():
    client=TestClient(app)
    client.__enter__()
    session=client.get("/api/v1/session")
    assert session.status_code==200
    return client,{"X-CSRF-Token":session.json()["csrf_token"]}


def test_transaction_page_contract_supports_pagination_and_filters():
    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code==200
        response=client.get(
            "/api/v1/transactions/page",
            params={"page":1,"page_size":25,"q":"","start":"2020-01-01","end":"2040-12-31"},
        )
        assert response.status_code==200
        data=response.json()
        assert set(("items","total","page","page_size","pages")).issubset(data)
        assert data["page_size"]==25
        assert isinstance(data["items"],list)


def test_tax_routes_accept_current_and_compatibility_methods():
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        payload={
            "jurisdiction":"ES",
            "tax_year":2099,
            "autonomous_community":"Madrid",
            "filing_status":"individual",
            "adults":1,
            "dependent_children":0,
            "children_under_three":0,
            "primary_residence":True,
        }
        current=client.put("/api/v1/tax/profile",json=payload,headers=headers)
        compat=client.post("/api/v1/tax/profile",json=payload,headers=headers)
        estimate=client.post("/api/v1/tax/estimate",json={"jurisdiction":"ES","tax_year":2099},headers=headers)
        estimate_get=client.get("/api/v1/tax/estimate?jurisdiction=ES&tax_year=2099")
        assert current.status_code==200
        assert compat.status_code==200
        assert estimate.status_code==200
        assert estimate_get.status_code==200


def test_ai_test_route_does_not_return_method_not_allowed(monkeypatch):
    monkeypatch.setattr(
        "financito.routes_config.ai_diagnose",
        lambda:{"available":True,"configured_model":"test","embedding_model":None,"models":["test"],"generation_ok":True,"latency_ms":1,"sample":"OK"},
    )
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        post=client.post("/api/v1/ai/test",headers=headers)
        get=client.get("/api/v1/ai/test")
        assert post.status_code==200
        assert get.status_code==200
        assert post.json()["generation_ok"] is True


def test_document_upload_accepts_post_and_put_methods():
    with TestClient(app) as client:
        session=client.get("/api/v1/session")
        headers={"X-CSRF-Token":session.json()["csrf_token"]}
        files={"files":("invalid.png",b"this-is-not-a-png","image/png")}
        post=client.post("/api/v1/documents/upload",files=files,headers=headers)
        files={"files":("invalid.png",b"this-is-not-a-png","image/png")}
        put=client.put("/api/v1/documents/upload",files=files,headers=headers)
        # Invalid image content is rejected as data, proving both verbs reached
        # the upload handler instead of failing at routing with HTTP 405.
        assert post.status_code==400
        assert put.status_code==400


def test_wealth_details_has_complete_summary_shape():
    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code==200
        response=client.get("/api/v1/wealth/details")
        assert response.status_code==200
        data=response.json()
        assert set(("summary","accounts","assets","liabilities","mortgages","investments","insurance")).issubset(data)
        assert "net_worth" in data["summary"]
        assert "annual_premium_total" in data["insurance"]


def test_stooq_normalizes_bare_us_tickers_for_free_fallback():
    assert StooqProvider.normalize_symbol("AAPL")=="aapl.us"
    assert StooqProvider.normalize_symbol("aapl.us")=="aapl.us"
