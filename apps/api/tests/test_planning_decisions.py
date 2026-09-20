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
            account_id=account.id, booking_date=today, amount=Decimal("-999999"),
            base_amount=Decimal("-999999"), currency="EUR", base_currency="EUR",
            description_raw=f"Compra {suffix}", description_normalized=f"compra {suffix}",
            merchant_raw=f"Tienda {suffix}", merchant_normalized=f"tienda {suffix}",
            duplicate_fingerprint=f"chat-expense-{suffix}",
        )
        refund = Transaction(
            account_id=account.id, booking_date=today, amount=Decimal("999999"),
            base_amount=Decimal("999999"), currency="EUR", base_currency="EUR",
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
        assert Decimal(result["calculations"]["cash_flow"]["income"]) < Decimal("999999")
        assert Decimal(result["calculations"]["cash_flow"]["expenses"]) < Decimal("999999")



def test_decision_lab_uses_saved_mortgage_and_live_context():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        headers = _session(client)
        created = client.post(
            "/api/v1/mortgages",
            headers=headers,
            json={
                "lender": f"Banco {suffix}",
                "remaining_principal": "150000",
                "currency": "EUR",
                "interest_type": "fixed",
                "nominal_rate": "0.03",
                "monthly_payment": "832",
                "remaining_months": 240,
                "early_repayment_fee": "100",
            },
        )
        assert created.status_code == 200
        mortgage_id = created.json()["id"]

        current = client.post("/api/v1/decision-lab/mortgage/current", headers=headers, json={"mortgage_id": mortgage_id})
        assert current.status_code == 200
        assert current.json()["mortgage"]["remaining_principal"] == "150000.0000"
        assert current.json()["source"] == "saved_mortgage"

        prepay = client.post(
            "/api/v1/decision-lab/mortgage/prepayment",
            headers=headers,
            json={"mortgage_id": mortgage_id, "extra_payment": "10000"},
        )
        assert prepay.status_code == 200
        assert prepay.json()["assumption"]["extra_payment"] == "10000"

        path = client.post(
            "/api/v1/decision-lab/mortgage/rate-path",
            headers=headers,
            json={"mortgage_id": mortgage_id, "rate_steps": [{"month": 13, "annual_rate": "0.04"}]},
        )
        assert path.status_code == 200
        assert path.json()["mortgage"]["id"] == mortgage_id
        assert len(path.json()["segments"]) >= 2

        decision = client.post(
            "/api/v1/decisions",
            headers=headers,
            json={"decision_type": "mortgage", "question": f"Amortizar {suffix}", "current_state": {}, "assumptions": {}, "constraints": {}},
        )
        assert decision.status_code == 200
        detail = client.get("/api/v1/decisions/" + decision.json()["id"])
        assert detail.status_code == 200
        assert any(x["id"] == mortgage_id for x in detail.json()["live_current_state"]["mortgages"])
        assert detail.json()["current_state"]["captured_from"] == "live_financito_data"



def test_month_end_projection_uses_history_and_keeps_unallocated_commitments_out_of_account_balances():
    from datetime import date
    from decimal import Decimal
    from financito.db import SessionLocal
    from financito.models import Account, Commitment, Transaction
    from financito.services.month_end import month_end_projection

    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        account = Account(
            name=f"Cuenta cierre {suffix}",
            institution_name="Banco test",
            current_balance=Decimal("1000"),
            currency="EUR",
        )
        db.add(account)
        db.flush()

        def tx(day, amount, description):
            return Transaction(
                account_id=account.id,
                booking_date=day,
                amount=Decimal(amount),
                base_amount=Decimal(amount),
                currency="EUR",
                base_currency="EUR",
                description_raw=description,
                description_normalized=description.lower(),
                duplicate_fingerprint=f"{suffix}-{description}-{day.isoformat()}",
            )

        db.add_all([
            tx(date(2025, 9, 22), "200", "income-last-year"),
            tx(date(2025, 9, 25), "-100", "expense-last-year"),
            tx(date(2026, 9, 1), "120", "income-current"),
            tx(date(2026, 9, 10), "-50", "expense-current"),
        ])
        db.add(Commitment(
            commitment_type="manual",
            title=f"Seguro {suffix}",
            amount=Decimal("120"),
            currency="EUR",
            due_date=date(2026, 9, 27),
            confidence=Decimal("1"),
            mandatory=True,
            cancellable=False,
            status="active",
        ))
        db.commit()

        result = month_end_projection(db, date(2026, 9, 20))
        row = next(x for x in result["accounts"] if x["id"] == account.id)

        assert Decimal(row["projected_remaining_income"]) == Decimal("146.00")
        assert Decimal(row["projected_remaining_expenses"]) == Decimal("72.50")
        assert Decimal(row["projected_closing_balance"]) == Decimal("1073.50")
        assert Decimal(result["forecast_remaining"]["known_commitments"]) >= Decimal("120")
        assert "70% mismo periodo" in row["method"]
