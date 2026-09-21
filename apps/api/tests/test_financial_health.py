from datetime import date,timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from financito.db import SessionLocal
from financito.main import app
from financito.models import Account,Commitment,FinancialGoal,Transaction
from financito.models_analytics import RecurringPreference,RecurringSeries
from financito.services.calendar import events
from financito.services.categorization import ensure_categories
from financito.services.financial_analytics import ESSENTIAL,spending_structure
from financito.services.financial_health import financial_health_summary


def _csrf(client:TestClient):
    return {"X-CSRF-Token":client.get("/api/v1/session").json()["csrf_token"]}


def _transaction(db,account_id,when,amount,merchant,category_id,recurring=False):
    row=Transaction(
        account_id=account_id,booking_date=when,amount=Decimal(str(amount)),base_amount=Decimal(str(amount)),
        currency="EUR",base_currency="EUR",description_raw=merchant,description_normalized=merchant.lower(),
        merchant_raw=merchant,merchant_normalized=merchant.lower(),category_id=category_id,
        categorization_method="test",categorization_confidence=Decimal("1"),user_verified=True,
        is_internal_transfer=False,is_recurring=recurring,is_extraordinary=False,duplicate_fingerprint=uuid4().hex,
    )
    db.add(row);return row


def test_goal_allocations_never_double_count_account_balance():
    suffix=uuid4().hex[:8]
    with TestClient(app) as client:
        headers=_csrf(client)
        account=client.post("/api/v1/accounts",json={"name":"Bolsa "+suffix,"current_balance":"5000","available_balance":"5000"},headers=headers)
        assert account.status_code==200
        account_id=account.json()["id"]
        first=client.post("/api/v1/goals",json={
            "goal_type":"travel","name":"Vacaciones "+suffix,"target_amount":"3000","account_id":account_id,
            "allocated_amount":"3000","planned_monthly_contribution":"0","priority":"medium",
        },headers=headers)
        assert first.status_code==200 and Decimal(first.json()["current_amount"])==Decimal("3000")
        rejected=client.post("/api/v1/goals",json={
            "goal_type":"car","name":"Coche "+suffix,"target_amount":"10000","account_id":account_id,
            "allocated_amount":"2500","planned_monthly_contribution":"0","priority":"medium",
        },headers=headers)
        assert rejected.status_code==409
        assert "quedan 2000" in rejected.json()["detail"]
        second=client.post("/api/v1/goals",json={
            "goal_type":"car","name":"Coche "+suffix,"target_amount":"10000","account_id":account_id,
            "allocated_amount":"2000","planned_monthly_contribution":"0","priority":"medium",
        },headers=headers)
        assert second.status_code==200 and Decimal(second.json()["current_amount"])==Decimal("2000")
        goals=client.get("/api/v1/goals?account_id="+account_id).json()
        assert sum(Decimal(x["allocated_amount"]) for x in goals)==Decimal("5000")
        for goal in goals:client.delete("/api/v1/goals/"+goal["id"],headers=headers)
        assert client.delete("/api/v1/accounts/"+account_id,headers=headers).status_code==200


def test_budget_household_and_account_scopes_are_not_mixed():
    suffix=uuid4().hex[:8]
    with TestClient(app) as client:
        headers=_csrf(client)
        account=client.post("/api/v1/accounts",json={"name":"Presupuesto "+suffix,"current_balance":"1000"},headers=headers).json()
        category=next(x for x in client.get("/api/v1/categories").json() if x["system_key"]=="groceries")
        household=client.post("/api/v1/budgets",json={"category_id":category["id"],"amount":"650","period_type":"monthly","alert_threshold":"0.8"},headers=headers)
        scoped=client.post("/api/v1/budgets",json={"category_id":category["id"],"account_id":account["id"],"amount":"300","period_type":"monthly","alert_threshold":"0.8"},headers=headers)
        assert household.status_code==200 and scoped.status_code==200
        household_rows=client.get("/api/v1/budgets").json()
        scoped_rows=client.get("/api/v1/budgets?account_id="+account["id"]).json()
        assert any(x["id"]==household.json()["id"] and x["scope"]=="household" for x in household_rows)
        assert all(x["id"]!=scoped.json()["id"] for x in household_rows)
        assert any(x["id"]==scoped.json()["id"] and x["scope"]=="account" for x in scoped_rows)
        assert all(x["id"]!=household.json()["id"] for x in scoped_rows)
        client.delete("/api/v1/budgets/"+household.json()["id"],headers=headers)
        client.delete("/api/v1/budgets/"+scoped.json()["id"],headers=headers)
        client.delete("/api/v1/accounts/"+account["id"],headers=headers)


def test_commitment_can_be_added_for_household_without_account_and_deleted():
    suffix=uuid4().hex[:8]
    due=(date.today()+timedelta(days=12)).isoformat()
    with TestClient(app) as client:
        headers=_csrf(client)
        created=client.post("/api/v1/commitments",json={
            "account_id":None,"commitment_type":"manual","title":"IBI "+suffix,"amount":"320",
            "currency":"EUR","due_date":due,"mandatory":True,"cancellable":False,
        },headers=headers)
        assert created.status_code==200
        commitment_id=created.json()["id"]
        assert any(x["id"]==commitment_id and x["account_id"] is None for x in client.get("/api/v1/commitments").json())
        assert client.delete("/api/v1/commitments/"+commitment_id,headers=headers).status_code==200


def test_not_subscription_preference_removes_recurring_projection():
    merchant="recurrent-not-subscription-"+uuid4().hex[:8]
    with SessionLocal() as db:
        row=RecurringSeries(
            merchant_normalized=merchant,cadence="monthly",expected_amount=Decimal("25"),
            amount_tolerance=Decimal("3"),next_expected_date=date.today()+timedelta(days=5),
            confidence=Decimal("0.90"),status="active",
        )
        db.add(row);db.commit();series_id=row.id
    with TestClient(app) as client:
        headers=_csrf(client);start=date.today();end=start+timedelta(days=40)
        before=client.get(f"/api/v1/calendar?start={start}&end={end}").json()["events"]
        assert any(x["type"]=="recurring" and merchant in x["title"] for x in before)
        updated=client.patch("/api/v1/recurring/"+series_id,json={"action":"not_subscription","essential_override":False,"contract_id":None},headers=headers)
        assert updated.status_code==200 and updated.json()["projected"] is False
        after=client.get(f"/api/v1/calendar?start={start}&end={end}").json()["events"]
        assert not any(x["type"]=="recurring" and merchant in x["title"] for x in after)
    with SessionLocal() as db:
        db.execute(delete(RecurringPreference).where(RecurringPreference.merchant_key==merchant))
        row=db.get(RecurringSeries,series_id)
        if row:db.delete(row)
        db.commit()


def test_spending_structure_is_exclusive_and_safe_to_spend_protects_reserved_money():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        cats=ensure_categories(db)
        account=Account(name="Health "+suffix,current_balance=Decimal("1000"),available_balance=Decimal("1000"),source="manual")
        db.add(account);db.flush();today=date.today()
        _transaction(db,account.id,today,"-100","Luz "+suffix,cats["utilities"].id,True)
        _transaction(db,account.id,today,"-20","Streaming "+suffix,cats["subscriptions"].id,True)
        _transaction(db,account.id,today,"-150","Supermercado "+suffix,cats["groceries"].id,False)
        discretionary=next(category for key,category in cats.items() if key not in ESSENTIAL)
        _transaction(db,account.id,today,"-50","Ocio "+suffix,discretionary.id,False)
        goal=FinancialGoal(
            account_id=account.id,goal_type="travel",name="Reserva "+suffix,target_amount=Decimal("1000"),
            current_amount=Decimal("0"),allocated_amount=Decimal("600"),planned_monthly_contribution=Decimal("0"),status="active",
        )
        db.add(goal);db.commit()
        structure=spending_structure(db,today,today,account.id,None)
        total=sum(Decimal(structure[k]) for k in ("fixed_essential","fixed_optional","variable_essential","discretionary"))
        assert total==Decimal(structure["total"])==Decimal("320.00")
        health=financial_health_summary(db,as_of=today,start=today,end=today,account_id=account.id)
        assert Decimal(health["safe_to_spend"]["reserved_goals"])==Decimal("600.00")
        assert Decimal("0")<=Decimal(health["safe_to_spend"]["amount"])<=Decimal("400.00")
        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(goal);db.delete(account);db.commit()


def test_available_to_spend_exposes_selected_period_spending_rate_without_treating_past_as_today():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        cats=ensure_categories(db)
        discretionary=[category for key,category in cats.items() if key not in ESSENTIAL]
        assert len(discretionary)>=2
        account=Account(
            name="Period health "+suffix,current_balance=Decimal("10000"),
            available_balance=Decimal("10000"),source="manual",
        )
        db.add(account);db.flush()
        today=date.today()
        previous=today-timedelta(days=30)
        _transaction(db,account.id,previous,"-10","Low spend "+suffix,discretionary[0].id,False)
        _transaction(db,account.id,today,"-100","High spend "+suffix,discretionary[1].id,False)
        db.commit()

        past=financial_health_summary(db,as_of=today,start=previous,end=previous,account_id=account.id)
        current=financial_health_summary(db,as_of=today,start=today,end=today,account_id=account.id)

        assert past["safe_to_spend"]["mode"]=="historical"
        assert past["safe_to_spend"]["historical_outcome"] is not None
        assert current["safe_to_spend"]["mode"]=="current"
        assert Decimal(current["safe_to_spend"]["selected_monthly_spending"])==Decimal("3000.00")

        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account);db.commit()


def test_available_to_spend_includes_expected_salary_not_yet_received():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        cats=ensure_categories(db)
        salary_category=next(iter(cats.values()))
        account=Account(
            name="Salary health "+suffix,current_balance=Decimal("1000"),
            available_balance=Decimal("1000"),source="manual",
        )
        db.add(account);db.flush()
        today=date.today()
        for days in (85,55,25):
            _transaction(db,account.id,today-timedelta(days=days),"2000","Nomina "+suffix,salary_category.id,False)
        db.commit()

        health=financial_health_summary(db,as_of=today,start=today.replace(day=1),end=today,account_id=account.id)
        safe=health["safe_to_spend"]

        assert safe["mode"]=="current"
        assert Decimal(safe["expected_income_before_horizon"])==Decimal("2000.00")
        assert len(safe["expected_incomes"])==1
        assert Decimal(safe["amount"])>=Decimal("3000.00")

        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account);db.commit()


def test_closed_period_returns_consolidated_actual_vs_reconstructed_forecast():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        cats=ensure_categories(db)
        category=next(iter(cats.values()))
        account=Account(
            name="Historical health "+suffix,current_balance=Decimal("99999"),
            available_balance=Decimal("99999"),source="manual",
        )
        db.add(account);db.flush()
        today=date.today()
        previous_end=today.replace(day=1)-timedelta(days=1)
        previous_start=previous_end.replace(day=1)
        actual_income_day=min(5,previous_end.day)
        actual_expense_day=min(12,previous_end.day)
        _transaction(db,account.id,previous_start.replace(day=actual_income_day),"3000","Income actual "+suffix,category.id,False)
        _transaction(db,account.id,previous_start.replace(day=actual_expense_day),"-1000","Expense actual "+suffix,category.id,False)
        ly_start=previous_start.replace(year=previous_start.year-1)
        _transaction(db,account.id,ly_start.replace(day=actual_income_day),"2800","Income ly "+suffix,category.id,False)
        _transaction(db,account.id,ly_start.replace(day=actual_expense_day),"-1200","Expense ly "+suffix,category.id,False)
        db.commit()

        health=financial_health_summary(db,as_of=today,start=previous_start,end=previous_end,account_id=account.id)
        safe=health["safe_to_spend"]
        outcome=safe["historical_outcome"]

        assert safe["mode"]=="historical"
        assert outcome is not None
        assert Decimal(outcome["actual_income"])==Decimal("3000.00")
        assert Decimal(outcome["actual_expenses"])==Decimal("1000.00")
        assert Decimal(outcome["actual_savings"])==Decimal("2000.00")
        assert Decimal(outcome["savings_variance"])==Decimal(outcome["actual_savings"])-Decimal(outcome["forecast_savings"])
        assert outcome["forecast_kind"]=="reconstructed"

        db.execute(delete(Transaction).where(Transaction.account_id==account.id))
        db.delete(account);db.commit()


def test_recurring_manual_commitment_repeats_in_calendar():
    suffix=uuid4().hex[:8]
    with SessionLocal() as db:
        row=Commitment(
            account_id=None,commitment_type="manual",title="Colegio "+suffix,amount=Decimal("200"),
            currency="EUR",due_date=date.today()-timedelta(days=35),recurrence="monthly",confidence=Decimal("1"),
            source_type="manual",mandatory=True,cancellable=False,status="active",
        )
        db.add(row);db.commit()
        matches=[x for x in events(db,date.today(),date.today()+timedelta(days=70)) if x["type"]=="commitment" and x["title"]=="Colegio "+suffix]
        assert len(matches)>=2
        db.delete(row);db.commit()
