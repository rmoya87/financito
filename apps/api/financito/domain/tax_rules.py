from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class TaxBracket:
    upper_bound: Decimal | None
    rate: Decimal


@dataclass(frozen=True)
class SavingsIntegration:
    taxable_base: Decimal
    offset_from_investment_income: Decimal
    offset_from_capital_gains: Decimal
    carryforward_investment_income: Decimal
    carryforward_capital_gains: Decimal


@dataclass(frozen=True)
class SavingsTaxRuleSet:
    jurisdiction: str
    tax_year: int
    version: str
    brackets: tuple[TaxBracket, ...]
    cross_offset_limit: Decimal
    carryforward_years: int
    legal_references: tuple[str, ...]
    source_urls: tuple[str, ...]
    verified_on: str

    def integrate_current_year(self, investment_income_net: Decimal, capital_gains_net: Decimal) -> SavingsIntegration:
        income = Decimal(investment_income_net)
        gains = Decimal(capital_gains_net)
        income_offset = Decimal("0")
        gains_offset = Decimal("0")
        carry_income = Decimal("0")
        carry_gains = Decimal("0")
        if income >= 0 and gains >= 0:
            taxable = income + gains
        elif income < 0 and gains > 0:
            income_offset = min(-income, gains * self.cross_offset_limit)
            taxable = gains - income_offset
            carry_income = (-income) - income_offset
        elif gains < 0 and income > 0:
            gains_offset = min(-gains, income * self.cross_offset_limit)
            taxable = income - gains_offset
            carry_gains = (-gains) - gains_offset
        else:
            taxable = Decimal("0")
            carry_income = max(Decimal("0"), -income)
            carry_gains = max(Decimal("0"), -gains)
        return SavingsIntegration(
            taxable.quantize(MONEY, rounding=ROUND_HALF_UP),
            income_offset.quantize(MONEY, rounding=ROUND_HALF_UP),
            gains_offset.quantize(MONEY, rounding=ROUND_HALF_UP),
            carry_income.quantize(MONEY, rounding=ROUND_HALF_UP),
            carry_gains.quantize(MONEY, rounding=ROUND_HALF_UP),
        )

    def tax_for_base(self, taxable_base: Decimal) -> Decimal:
        base = max(Decimal("0"), Decimal(taxable_base))
        tax = Decimal("0")
        lower = Decimal("0")
        for bracket in self.brackets:
            amount = max(Decimal("0"), base - lower) if bracket.upper_bound is None else max(Decimal("0"), min(base, bracket.upper_bound) - lower)
            tax += amount * bracket.rate
            if bracket.upper_bound is None or base <= bracket.upper_bound:
                break
            lower = bracket.upper_bound
        return tax.quantize(MONEY, rounding=ROUND_HALF_UP)


_ES_2025 = SavingsTaxRuleSet(
    jurisdiction="ES",
    tax_year=2025,
    version="ES-IRPF-ahorro-2025-v1",
    brackets=(
        TaxBracket(Decimal("6000"), Decimal("0.19")),
        TaxBracket(Decimal("50000"), Decimal("0.21")),
        TaxBracket(Decimal("200000"), Decimal("0.23")),
        TaxBracket(Decimal("300000"), Decimal("0.27")),
        TaxBracket(None, Decimal("0.30")),
    ),
    cross_offset_limit=Decimal("0.25"),
    carryforward_years=4,
    legal_references=(
        "Ley 35/2006 (LIRPF), arts. 46, 49, 66 y 76",
        "Ley 7/2024, disposición final séptima, efectos desde 2025-01-01",
    ),
    source_urls=(
        "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        "https://www.boe.es/buscar/act.php?id=BOE-A-2024-26694",
        "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/8-cumplimentacion-irpf/8_4-cuota-integra/8_4_4-gravamen-base-liquidable-ahorro.html",
    ),
    verified_on="2026-09-20",
)

_ES_2026 = SavingsTaxRuleSet(
    jurisdiction="ES",
    tax_year=2026,
    version="ES-IRPF-ahorro-2026-v1",
    brackets=_ES_2025.brackets,
    cross_offset_limit=_ES_2025.cross_offset_limit,
    carryforward_years=_ES_2025.carryforward_years,
    legal_references=_ES_2025.legal_references,
    source_urls=_ES_2025.source_urls,
    verified_on="2026-09-20",
)

_RULES: dict[tuple[str, int], SavingsTaxRuleSet] = {
    ("ES", 2025): _ES_2025,
    ("ES", 2026): _ES_2026,
}


def get_savings_rules(jurisdiction: str, tax_year: int) -> SavingsTaxRuleSet | None:
    return _RULES.get((jurisdiction.strip().upper(), int(tax_year)))


def supported_savings_rules() -> tuple[SavingsTaxRuleSet, ...]:
    return tuple(_RULES[key] for key in sorted(_RULES))
