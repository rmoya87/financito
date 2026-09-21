from datetime import date
import json
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete

from financito.db import SessionLocal
from financito.models import Account,Budget,Category,Document,ExtractedFact,Mortgage,Transaction
from financito.models_analytics import Anomaly,EntityLink
from financito.services.decision_context import live_decision_context
from financito.services.decision_support import decision_overview


def test_decision_context_crosses_mortgage_budget_anomaly_and_cashflow():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        category=Category(name=f"Decisión {suffix}",system_key=f"decision_{suffix}")
        account=Account(
            name=f"Cuenta decisión {suffix}",
            institution_name="Banco test",
            account_type="checking",
            currency="EUR",
            current_balance=Decimal("20000"),
        )
        mortgage=Mortgage(
            lender=f"Banco hipoteca {suffix}",
            remaining_principal=Decimal("100000"),
            currency="EUR",
            interest_type="fixed",
            nominal_rate=Decimal("0.03"),
            monthly_payment=Decimal("650"),
            remaining_months=180,
            early_repayment_fee=Decimal("100"),
        )
        db.add_all([category,account,mortgage]);db.flush()
        document=Document(
            file_path=f"/tmp/decision-{suffix}.pdf",
            file_name=f"decision-{suffix}.pdf",
            mime_type="application/pdf",
            sha256=(suffix*8)[:64],
            document_type="mortgage",
            status="indexed",
            page_count=1,
            extracted_text="Amortización parcial permitida; puede reducir cuota o plazo.",
        )
        db.add(document);db.flush()
        db.add(EntityLink(
            from_type="document",from_id=document.id,relation_type="evidence_for",
            to_type="mortgage",to_id=mortgage.id,confidence=Decimal("1"),
            source_type="test",source_ref=document.id,
        ))
        for key,value,unit in (
            ("partial_prepayment_allowed","true","boolean"),
            ("prepayment_reduction_options","both","enum"),
            ("prepayment_notice_days","0","days"),
        ):
            db.add(ExtractedFact(
                document_id=document.id,fact_type="mortgage_term",key=key,
                value_json=json.dumps({"value":value,"unit":unit}),
                confidence=Decimal("0.99"),status="confirmed",source_page=1,
                source_section="test",user_verified=True,
            ))
        db.flush()
        budget=Budget(
            category_id=category.id,
            period_type="monthly",
            amount=Decimal("1000"),
            currency="EUR",
            alert_threshold=Decimal("0.8"),
        )
        tx=Transaction(
            account_id=account.id,
            booking_date=date.today(),
            amount=Decimal("-900"),
            base_amount=Decimal("-900"),
            currency="EUR",
            base_currency="EUR",
            description_raw=f"Gasto decisión {suffix}",
            description_normalized=f"gasto decision {suffix}",
            merchant_raw="Comercio test",
            merchant_normalized="comercio test",
            category_id=category.id,
            categorization_method="manual",
            categorization_confidence=Decimal("1"),
            user_verified=True,
            is_internal_transfer=False,
            is_recurring=False,
            is_extraordinary=False,
            duplicate_fingerprint=f"decision-{suffix}",
            source="test",
        )
        db.add_all([budget,tx]);db.flush()
        anomaly=Anomaly(
            transaction_id=tx.id,
            anomaly_type="amount_spike",
            baseline_json='{"median":"100"}',
            observed_json='{"amount":"900"}',
            explanation="El importe supera claramente el patrón reciente.",
            confidence=Decimal("0.95"),
            status="open",
        )
        db.add(anomaly);db.commit()

        context=live_decision_context(db)
        mortgage_row=next(row for row in context["mortgages"] if row["id"]==mortgage.id)
        assert mortgage_row["current_remaining_apr"]["status"]=="estimated"
        assert mortgage_row["switching_readiness"]["ready"] is True
        assert any(row["kind"]=="budget" and row["source_id"]==budget.id for row in context["decision_alerts"])
        assert any(row["kind"]=="transaction_anomaly" and row["source_id"]==tx.id for row in context["decision_alerts"])

        overview=decision_overview(db,mortgage.id)
        switch=next(row for row in overview["choice_cards"] if row["id"]=="mortgage-switch")
        assert switch["status"]=="ready_for_market_check"
        assert overview["prepayment_guardrail"]["status"]=="illustrative"
        assert overview["prepayment_guardrail"]["restrictions"]["partial_prepayment_allowed"] is True
        assert Decimal(overview["prepayment_guardrail"]["protected_liquidity_reference"])>0

        db.execute(delete(Anomaly).where(Anomaly.id==anomaly.id))
        db.delete(budget);db.delete(tx);db.delete(mortgage);db.delete(account);db.delete(category);db.commit()
