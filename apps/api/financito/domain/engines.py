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


@dataclass(frozen=True)
class MortgageRatePathSegment:
    start_month:int
    annual_rate:Decimal
    monthly_payment:Decimal
    end_balance:Decimal

@dataclass(frozen=True)
class MortgageRatePathResult:
    total_payments:Decimal
    total_interest:Decimal
    min_monthly_payment:Decimal
    max_monthly_payment:Decimal
    final_balance:Decimal
    segments:tuple[MortgageRatePathSegment,...]

class MortgageRatePathEngine:
    @staticmethod
    def simulate(principal:Decimal,months:int,initial_annual_rate:Decimal,rate_steps:list[tuple[int,Decimal]])->MortgageRatePathResult:
        if principal<=0 or months<=0 or initial_annual_rate<0:
            raise ValueError("Invalid mortgage inputs")
        normalized={1:initial_annual_rate}
        for month,rate in rate_steps:
            if month<1 or month>months or rate<0:
                raise ValueError("Invalid rate step")
            normalized[int(month)]=rate
        changes=sorted(normalized.items())
        balance=principal
        total_interest=Decimal("0")
        total_payments=Decimal("0")
        payments=[]
        segments=[]
        current_rate=initial_annual_rate
        change_map=dict(changes)
        segment_start=1
        segment_payment=MortgageEngine.amortization(balance,current_rate,months).monthly_payment
        for month in range(1,months+1):
            if month in change_map and month!=segment_start:
                segments.append(MortgageRatePathSegment(segment_start,current_rate,segment_payment,money(balance)))
                current_rate=change_map[month]
                segment_start=month
                remaining=months-month+1
                segment_payment=MortgageEngine.amortization(balance,current_rate,remaining).monthly_payment
            elif month==1 and 1 in change_map:
                current_rate=change_map[1]
                segment_payment=MortgageEngine.amortization(balance,current_rate,months).monthly_payment
            monthly_rate=current_rate/Decimal("12")
            interest=balance*monthly_rate
            principal_paid=segment_payment-interest
            if month==months or principal_paid>=balance:
                payment=balance+interest
                principal_paid=balance
            else:
                payment=segment_payment
            balance=max(Decimal("0"),balance-principal_paid)
            total_interest+=interest
            total_payments+=payment
            payments.append(payment)
        segments.append(MortgageRatePathSegment(segment_start,current_rate,segment_payment,money(balance)))
        return MortgageRatePathResult(
            total_payments=money(total_payments),
            total_interest=money(total_interest),
            min_monthly_payment=money(min(payments)),
            max_monthly_payment=money(max(payments)),
            final_balance=money(balance),
            segments=tuple(segments),
        )


@dataclass(frozen=True)
class MortgageIndexedPathResult:
    status:str
    missing_revision_months:tuple[int,...]
    applied_rate_steps:tuple[tuple[int,Decimal],...]
    path:MortgageRatePathResult|None

class MortgageIndexedRateEngine:
    """Variable/mixed path from explicit contractual revision observations only."""
    @staticmethod
    def simulate(principal:Decimal,months:int,interest_type:str,revision_frequency_months:int,index_curve:list[tuple[int,Decimal]],spread:Decimal=Decimal("0"),fixed_period_months:int=0,fixed_annual_rate:Decimal|None=None,floor_rate:Decimal|None=None,cap_rate:Decimal|None=None)->MortgageIndexedPathResult:
        kind=interest_type.strip().lower()
        if kind not in {"variable","mixed"}:raise ValueError("interest_type must be variable or mixed")
        if principal<=0 or months<=0 or revision_frequency_months<=0:raise ValueError("Invalid indexed mortgage inputs")
        if floor_rate is not None and floor_rate<0:raise ValueError("floor_rate cannot be negative")
        if cap_rate is not None and cap_rate<0:raise ValueError("cap_rate cannot be negative")
        if floor_rate is not None and cap_rate is not None and floor_rate>cap_rate:raise ValueError("floor_rate cannot exceed cap_rate")
        if kind=="mixed":
            if fixed_period_months<=0 or fixed_period_months>=months:raise ValueError("mixed mortgage requires a fixed period inside the remaining term")
            if fixed_annual_rate is None or fixed_annual_rate<0:raise ValueError("mixed mortgage requires fixed_annual_rate")
            variable_start=fixed_period_months+1
        else:
            if fixed_period_months:raise ValueError("fixed_period_months only applies to mixed mortgages")
            variable_start=1
        curve={}
        for month,index_rate in index_curve:
            month=int(month);index_rate=Decimal(index_rate)
            if month<1 or month>months:raise ValueError("Index curve month outside mortgage term")
            if month in curve:raise ValueError("Duplicate index curve month")
            curve[month]=index_rate
        required=tuple(range(variable_start,months+1,revision_frequency_months))
        missing=tuple(month for month in required if month not in curve)
        if missing:return MortgageIndexedPathResult("needs_more_data",missing,(),None)
        applied=[]
        for month in required:
            annual=curve[month]+spread
            if floor_rate is not None:annual=max(annual,floor_rate)
            if cap_rate is not None:annual=min(annual,cap_rate)
            if annual<0:raise ValueError("Resulting annual rate cannot be negative")
            applied.append((month,annual))
        if kind=="mixed":
            initial=fixed_annual_rate;steps=applied
        else:
            initial=applied[0][1];steps=applied[1:]
        path=MortgageRatePathEngine.simulate(principal,months,initial,steps)
        return MortgageIndexedPathResult("ready",(),tuple(applied),path)
