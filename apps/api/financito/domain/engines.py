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
