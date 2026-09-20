from datetime import date
from decimal import Decimal
from financito.domain.engines import CashFlowEngine, MortgageEngine, MortgageRatePathEngine, MortgageIndexedRateEngine, OptimizationEngine, comparable_period_last_year

def test_cashflow_excludes_internal_transfers():
    result=CashFlowEngine.calculate([(Decimal("3000"),False),(Decimal("-1000"),False),(Decimal("-500"),True)])
    assert result.income==Decimal("3000.00") and result.expenses==Decimal("1000.00") and result.savings==Decimal("2000.00")

def test_optimization_requires_penalty_evidence():
    result=OptimizationEngine.calculate(Decimal("500"),Decimal("0"),None,Decimal("0"),Decimal("0"),Decimal("0")); assert result.status=="needs_more_data" and result.net_annual_benefit is None

def test_mortgage_zero_rate():
    result=MortgageEngine.amortization(Decimal("120000"),Decimal("0"),120); assert result.monthly_payment==Decimal("1000.00") and result.total_interest==Decimal("0.00")

def test_comparable_leap_day():
    start,end=comparable_period_last_year(date(2028,2,29),date(2028,3,31)); assert start==date(2027,2,28) and end==date(2027,3,31)


def test_variable_rate_path_recalculates_payment_without_predicting():
    flat=MortgageRatePathEngine.simulate(Decimal("200000"),240,Decimal("0.02"),[])
    rising=MortgageRatePathEngine.simulate(Decimal("200000"),240,Decimal("0.02"),[(13,Decimal("0.04")),(25,Decimal("0.05"))])
    assert flat.final_balance==Decimal("0.00")
    assert rising.final_balance==Decimal("0.00")
    assert rising.max_monthly_payment>flat.max_monthly_payment
    assert rising.total_interest>flat.total_interest
    assert [s.start_month for s in rising.segments]==[1,13,25]


def test_indexed_mixed_mortgage_requires_every_revision():
    missing=MortgageIndexedRateEngine.simulate(Decimal("150000"),36,"mixed",12,[(13,Decimal("0.02"))],Decimal("0.01"),12,Decimal("0.018"))
    assert missing.status=="needs_more_data" and missing.missing_revision_months==(25,)
    ready=MortgageIndexedRateEngine.simulate(Decimal("150000"),36,"mixed",12,[(13,Decimal("0.02")),(25,Decimal("0.025"))],Decimal("0.01"),12,Decimal("0.018"))
    assert ready.status=="ready" and ready.path is not None and ready.path.final_balance==Decimal("0.00")
    assert [m for m,_ in ready.applied_rate_steps]==[13,25]
