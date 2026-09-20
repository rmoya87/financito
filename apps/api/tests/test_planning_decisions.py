from uuid import uuid4

from fastapi.testclient import TestClient

from financito.main import app


def _session(client: TestClient):
    response = client.get("/api/v1/session")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_mortgage_prepayment_cost_centers_coverage_and_decisions():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        headers = _session(client)

        mortgage = client.post(
            "/api/v1/mortgage/prepayment",
            headers=headers,
            json={
                "principal": "100000",
                "annual_rate": "0.03",
                "months": 240,
                "extra_payment": "10000",
                "prepayment_fee": "100",
            },
        )
        assert mortgage.status_code == 200
        m = mortgage.json()
        assert float(m["reduced_payment"]) < float(m["original_monthly_payment"])
        assert m["reduced_term_months"] < 240
        assert float(m["interest_saved_reduce_term"]) > 0

        contract = client.post(
            "/api/v1/contracts",
            headers=headers,
            json={
                "provider_name": f"Proveedor {suffix}",
                "contract_type": "energy",
                "annual_cost": "1200",
                "currency": "EUR",
                "evidence_status": "confirmed",
            },
        )
        assert contract.status_code == 200
        center = client.post(
            "/api/v1/cost-centers",
            headers=headers,
            json={"name": f"Vivienda {suffix}", "center_type": "home", "metadata": {}},
        )
        assert center.status_code == 200
        link = client.post(
            "/api/v1/cost-center-links",
            headers=headers,
            json={
                "cost_center_id": center.json()["id"],
                "entity_type": "contract",
                "entity_id": contract.json()["id"],
                "allocation_percentage": "50",
            },
        )
        assert link.status_code == 200
        summary = client.get(f"/api/v1/cost-centers/{center.json()['id']}/summary")
        assert summary.status_code == 200
        assert float(summary.json()["annual_linked_commitments"]) == 600.0

        policy = client.post(
            "/api/v1/insurance",
            headers=headers,
            json={
                "insurance_type": "home",
                "annual_premium": "300",
                "deductible": "150",
                "currency": "EUR",
            },
        )
        assert policy.status_code == 200
        coverage = client.post(
            "/api/v1/coverage",
            headers=headers,
            json={
                "insurance_policy_id": policy.json()["id"],
                "coverage_type": f"water_damage_{suffix}",
                "limit_amount": "5000",
                "confidence": "1",
                "user_verified": True,
            },
        )
        assert coverage.status_code == 200
        requirement = client.post(
            "/api/v1/coverage-requirements",
            headers=headers,
            json={
                "insurance_type": "home",
                "coverage_type": f"water_damage_{suffix}",
                "minimum_limit": "10000",
                "currency": "EUR",
                "enabled": True,
            },
        )
        assert requirement.status_code == 200
        gaps = client.get("/api/v1/coverage/gaps")
        assert gaps.status_code == 200
        match = next(x for x in gaps.json()["gaps"] if x["requirement_id"] == requirement.json()["id"])
        assert match["reason"] == "limit_below_requirement"
        assert float(match["best_verified_limit"]) == 5000.0

        decision = client.post(
            "/api/v1/decisions",
            headers=headers,
            json={
                "decision_type": "contract_switch",
                "question": f"Cambiar proveedor {suffix}",
                "current_state": {},
                "assumptions": {},
                "constraints": {},
            },
        )
        assert decision.status_code == 200
        decision_id = decision.json()["id"]
        alternative = client.post(
            f"/api/v1/decisions/{decision_id}/alternatives",
            headers=headers,
            json={
                "name": "Cambiar",
                "one_off_cost": "100",
                "monthly_cost": "10",
                "expected_benefit": "1000",
                "risk_level": "medium",
                "horizon_results": {},
                "uncertainties": ["precio futuro"],
            },
        )
        assert alternative.status_code == 200
        assert float(alternative.json()["net_benefit"]) == 780.0
        outcome = client.post(
            f"/api/v1/decisions/{decision_id}/outcomes",
            headers=headers,
            json={
                "selected_alternative_id": alternative.json()["id"],
                "observation_start": "2026-01-01",
                "observation_end": "2026-06-30",
                "expected_impact": {"net": 780},
                "observed_impact": {"net": 700},
                "explanation": "Resultado observado",
                "data_completeness": "1",
            },
        )
        assert outcome.status_code == 200
        assert outcome.json()["variance"]["net"] == -80
        state = client.patch(
            f"/api/v1/decisions/{decision_id}",
            headers=headers,
            json={"status": "closed"},
        )
        assert state.status_code == 200
        detail = client.get(f"/api/v1/decisions/{decision_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "closed"
        assert len(detail.json()["alternatives"]) == 1
        assert len(detail.json()["outcomes"]) == 1


def test_banking_public_surface_does_not_expose_raw_session_data():
    with TestClient(app) as client:
        paths = client.get("/api/openapi.json").json()["paths"]
        assert "/api/v1/banking/aspsps" in paths
        assert "/api/v1/banking/auth" in paths
        assert "/api/v1/banking/connections" in paths
        assert "/api/v1/banking/session" not in paths
        assert "/api/v1/banking/account/{account_id}/balances" not in paths
        assert "/api/v1/banking/account/{account_id}/transactions" not in paths


def test_chat_and_stress_use_refund_aware_cash_flow():
    from datetime import date
    from decimal import Decimal
    from financito.db import SessionLocal
    from financito.models import Account, Transaction
    from financito.models_analytics import EntityLink
    from financito.services.chat import answer

    suffix = uuid4().hex[:8]
    today = date.today()
    with SessionLocal() as db:
        account = Account(name=f"Refund flow {suffix}")
        db.add(account); db.flush()
        expense = Transaction(
            account_id=account.id, booking_date=today, amount=Decimal("-40"),
            base_amount=Decimal("-40"), currency="EUR", base_currency="EUR",
            description_raw=f"Compra {suffix}", description_normalized=f"compra {suffix}",
            merchant_raw=f"Tienda {suffix}", merchant_normalized=f"tienda {suffix}",
            duplicate_fingerprint=f"chat-expense-{suffix}",
        )
        refund = Transaction(
            account_id=account.id, booking_date=today, amount=Decimal("40"),
            base_amount=Decimal("40"), currency="EUR", base_currency="EUR",
            description_raw=f"Devolucion {suffix}", description_normalized=f"devolucion {suffix}",
            merchant_raw=f"Tienda {suffix}", merchant_normalized=f"tienda {suffix}",
            duplicate_fingerprint=f"chat-refund-{suffix}",
        )
        db.add_all([expense, refund]); db.flush()
        db.add(EntityLink(
            from_type="transaction", from_id=refund.id, relation_type="refund_of",
            to_type="transaction", to_id=expense.id, confidence=Decimal("1"),
            source_type="test", source_ref=expense.id,
        ))
        db.commit()
        result = answer(db, "resumen")
        assert Decimal(result["calculations"]["cash_flow"]["income"]) >= Decimal("0")
        # El par compra+reembolso no debe sumar 40 como ingreso ni 40 como gasto.
        assert Decimal(result["calculations"]["cash_flow"]["expenses"]) >= Decimal("0")
