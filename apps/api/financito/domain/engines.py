from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


ZERO = Decimal("0")
CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CashFlowResult:
    income: Decimal
    expenses: Decimal
    savings: Decimal
    savings_rate: Decimal | None


class CashFlowEngine:
    @staticmethod
    def calculate(rows: Iterable[tuple[Decimal, bool]]) -> CashFlowResult:
        income = ZERO
        expenses = ZERO
        for amount, is_internal in rows:
            if is_internal:
                continue
            if amount >= 0:
                income += amount
            else:
                expenses += -amount
        savings = income - expenses
        rate = None if income == 0 else (savings / income).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return CashFlowResult(money(income), money(expenses), money(savings), rate)


@dataclass(frozen=True)
class OptimizationResult:
    status: str
    net_annual_benefit: Decimal | None
    break_even_months: Decimal | None


class OptimizationEngine:
    @staticmethod
    def calculate(
        gross_annual_saving: Decimal,
        switching_costs: Decimal,
        penalties: Decimal | None,
        lost_benefits: Decimal,
        additional_recurring_costs: Decimal,
        tax_impact: Decimal,
    ) -> OptimizationResult:
        if penalties is None:
            return OptimizationResult("needs_more_data", None, None)
        net = gross_annual_saving - switching_costs - penalties - lost_benefits - additional_recurring_costs - tax_impact
        monthly = net / Decimal("12")
        break_even = None
        if monthly > 0 and (switching_costs + penalties) > 0:
            break_even = ((switching_costs + penalties) / monthly).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return OptimizationResult("ready", money(net), break_even)


@dataclass(frozen=True)
class MortgageScenarioResult:
    monthly_payment: Decimal
    total_payments: Decimal
    total_interest: Decimal


class MortgageEngine:
    @staticmethod
    def amortization(principal: Decimal, annual_rate: Decimal, months: int) -> MortgageScenarioResult:
        if principal < 0 or months <= 0 or annual_rate < 0:
            raise ValueError("Invalid mortgage inputs")
        if annual_rate == 0:
            payment = principal / Decimal(months)
        else:
            monthly_rate = annual_rate / Decimal("12")
            factor = (Decimal("1") + monthly_rate) ** months
            payment = principal * monthly_rate * factor / (factor - Decimal("1"))
        payment = money(payment)
        total = money(payment * months)
        return MortgageScenarioResult(payment, total, money(total - principal))


def comparable_period_last_year(start: date, end: date) -> tuple[date, date]:
    def replace_year(d: date) -> date:
        try:
            return d.replace(year=d.year - 1)
        except ValueError:
            return d.replace(year=d.year - 1, day=28)
    return replace_year(start), replace_year(end)


@dataclass(frozen=True)
class MortgagePrepaymentResult:
    original_monthly_payment: Decimal
    original_total_interest: Decimal
    reduced_payment: Decimal
    reduced_payment_total_interest: Decimal
    reduced_term_months: int
    reduced_term_total_interest: Decimal
    prepayment_fee: Decimal
    interest_saved_reduce_payment: Decimal
    interest_saved_reduce_term: Decimal

class MortgagePrepaymentEngine:
    @staticmethod
    def _term_with_payment(principal:Decimal,annual_rate:Decimal,payment:Decimal,max_months:int=1200)->tuple[int,Decimal]:
        if principal<=0:return 0,Decimal("0")
        monthly_rate=annual_rate/Decimal("12")
        balance=principal;interest_total=Decimal("0")
        for month in range(1,max_months+1):
            interest=balance*monthly_rate
            interest_total+=interest
            principal_paid=payment-interest
            if principal_paid<=0:raise ValueError("Payment does not amortize principal")
            if principal_paid>=balance:return month,money(interest_total)
            balance-=principal_paid
        raise ValueError("Scenario exceeds supported term")

    @staticmethod
    def compare(principal:Decimal,annual_rate:Decimal,months:int,extra_payment:Decimal,prepayment_fee:Decimal=Decimal("0"))->MortgagePrepaymentResult:
        if extra_payment<0 or prepayment_fee<0:raise ValueError("Invalid prepayment inputs")
        if extra_payment>principal:extra_payment=principal
        original=MortgageEngine.amortization(principal,annual_rate,months)
        new_principal=principal-extra_payment
        reduce_payment=MortgageEngine.amortization(new_principal,annual_rate,months) if new_principal>0 else MortgageScenarioResult(Decimal("0"),Decimal("0"),Decimal("0"))
        term_months,term_interest=MortgagePrepaymentEngine._term_with_payment(new_principal,annual_rate,original.monthly_payment)
        return MortgagePrepaymentResult(
            original_monthly_payment=original.monthly_payment,
            original_total_interest=original.total_interest,
            reduced_payment=reduce_payment.monthly_payment,
            reduced_payment_total_interest=reduce_payment.total_interest,
            reduced_term_months=term_months,
            reduced_term_total_interest=term_interest,
            prepayment_fee=money(prepayment_fee),
            interest_saved_reduce_payment=money(original.total_interest-reduce_payment.total_interest-prepayment_fee),
            interest_saved_reduce_term=money(original.total_interest-term_interest-prepayment_fee),
        )
