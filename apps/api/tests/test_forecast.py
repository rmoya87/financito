from datetime import date
from decimal import Decimal
from financito.db import SessionLocal
from financito.models import Account, Commitment, Transaction
from financito.services.forecast import forecast

def add_tx(db,account_id,when,amount,label):
    db.add(Transaction(account_id=account_id,booking_date=when,amount=amount,base_amount=amount,currency="EUR",base_currency="EUR",description_raw=label,description_normalized=label.lower(),duplicate_fingerprint=f"{when}-{label}-{amount}"))

def test_forecast_uses_last_year_and_commitments():
    with SessionLocal() as db:
        account=Account(name="Forecast account",current_balance=Decimal("5000")); db.add(account); db.flush()
        add_tx(db,account.id,date(2025,10,5),Decimal("3000"),"salary-ly"); add_tx(db,account.id,date(2025,10,10),Decimal("-1000"),"expense-ly")
        db.add(Commitment(commitment_type="insurance",title="Seguro",amount=Decimal("200"),due_date=date(2026,10,20))); db.commit()
        result=forecast(db,date(2026,10,1),date(2026,10,31)); assert result.baseline_start==date(2025,10,1) and result.historical_baseline==Decimal("1000.00") and result.known_commitments==Decimal("200.00") and result.predicted_expenses>=Decimal("1000.00")
