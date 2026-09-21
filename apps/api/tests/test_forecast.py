from datetime import date
from decimal import Decimal
from financito.db import SessionLocal
from financito.models import Account, Commitment, Transaction
from financito.services.forecast import forecast
from financito.services import month_end as month_end_service

def add_tx(db,account_id,when,amount,label):
    db.add(Transaction(account_id=account_id,booking_date=when,amount=amount,base_amount=amount,currency="EUR",base_currency="EUR",description_raw=label,description_normalized=label.lower(),duplicate_fingerprint=f"{when}-{label}-{amount}"))

def test_forecast_uses_last_year_and_commitments():
    with SessionLocal() as db:
        account=Account(name="Forecast account",current_balance=Decimal("5000")); db.add(account); db.flush()
        add_tx(db,account.id,date(2025,10,5),Decimal("3000"),"salary-ly"); add_tx(db,account.id,date(2025,10,10),Decimal("-1000"),"expense-ly")
        db.add(Commitment(commitment_type="insurance",title="Seguro",amount=Decimal("200"),due_date=date(2026,10,20))); db.commit()
        result=forecast(db,date(2026,10,1),date(2026,10,31)); assert result.baseline_start==date(2025,10,1) and result.historical_baseline==Decimal("1000.00") and result.known_commitments==Decimal("200.00") and result.predicted_expenses>=Decimal("1000.00")


def test_month_end_projection_applies_historical_underprediction_correction(monkeypatch):
    with SessionLocal() as db:
        account=Account(name="Month end calibration",current_balance=Decimal("10000"))
        db.add(account);db.flush()
        add_tx(db,account.id,date(2026,9,10),Decimal("-1000"),"actual-current")
        db.commit()

        monkeypatch.setattr(
            month_end_service,
            "_remaining_projection_for_account",
            lambda session,account_id,as_of,end:{
                "income":Decimal("0"),"expenses":Decimal("1000"),
                "history_days":60,"method":"test history",
            },
        )
        monkeypatch.setattr(
            month_end_service,
            "_calendar_expense_floor",
            lambda session,start,end,account_id=None,account_type=None:{
                "known":Decimal("800"),"patterns":Decimal("700"),"floor":Decimal("800"),
            },
        )
        monkeypatch.setattr(
            month_end_service,
            "_backtest_accuracy",
            lambda session,as_of,months=6,account_id=None,account_type=None:{
                "months_evaluated":4,"expense_wape":"0.2000","expense_accuracy":"0.8000",
                "expense_bias":"-3100.00","typical_underprediction":"3100.00","savings_mae":"500.00",
            },
        )

        result=month_end_service.month_end_projection(db,date(2026,9,21),account_id=account.id)

        assert result["forecast_remaining"]["expenses_from_history"]=="1000.00"
        assert result["forecast_remaining"]["historical_underprediction_adjustment"]=="930.00"
        assert result["forecast_remaining"]["expenses"]=="1930.00"
        assert result["projected_month_end"]["expenses"]=="2930.00"

        db.query(Transaction).filter(Transaction.account_id==account.id).delete()
        db.delete(account);db.commit()
