from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models_extended import LotDisposal, Trade
from ..domain.tax_rules import get_savings_rules

Q=Decimal("0.01")

def _rule_payload(rule):
    return {
        "rule_version":rule.version,
        "legal_references":list(rule.legal_references),
        "sources":list(rule.source_urls),
        "verified_on":rule.verified_on,
        "cross_offset_limit":str(rule.cross_offset_limit),
        "carryforward_years":rule.carryforward_years,
    }

def estimate(session:Session,jurisdiction:str,tax_year:int,assumed_rate:Decimal|None=None)->dict:
    start=datetime(tax_year,1,1,tzinfo=timezone.utc);end=datetime(tax_year+1,1,1,tzinfo=timezone.utc)
    rows=session.execute(select(LotDisposal.realized_pnl).join(Trade,Trade.id==LotDisposal.trade_id).where(Trade.executed_at>=start,Trade.executed_at<end)).scalars().all()
    realized=sum(rows,Decimal("0")).quantize(Q)
    if assumed_rate is not None:
        tax=(max(Decimal("0"),realized)*assumed_rate).quantize(Q,rounding=ROUND_HALF_UP)
        return {"jurisdiction":jurisdiction.upper(),"tax_year":tax_year,"realized_pnl":str(realized),"estimated_tax":str(tax),"assumed_rate":str(assumed_rate),"status":"assumption_override","notice":"Escenario parametrizado por el usuario; no representa la liquidación oficial."}
    rule=get_savings_rules(jurisdiction,tax_year)
    if rule is None:
        return {"jurisdiction":jurisdiction.upper(),"tax_year":tax_year,"realized_pnl":str(realized),"estimated_tax":None,"assumed_rate":None,"status":"needs_rate","notice":"No hay módulo normativo verificado para esta jurisdicción/ejercicio. Introduce una tasa solo para simular."}
    integrated=rule.integrate_current_year(Decimal("0"),realized)
    tax=rule.tax_for_base(integrated.taxable_base)
    return {
        "jurisdiction":rule.jurisdiction,"tax_year":tax_year,"realized_pnl":str(realized),
        "taxable_savings_base_from_available_data":str(integrated.taxable_base),
        "estimated_tax":str(tax),"assumed_rate":None,"status":"normative_partial",
        "carryforward_capital_gains":str(integrated.carryforward_capital_gains),
        "missing_inputs":["rendimientos del capital mobiliario del ejercicio","saldos negativos pendientes de ejercicios anteriores","mínimo personal/familiar aplicable y otros ajustes de declaración"],
        **_rule_payload(rule),
        "notice":"Cálculo normativo parcial de la base del ahorro con los datos disponibles en Financito. No constituye una declaración fiscal completa.",
    }

def calculate_savings(jurisdiction:str,tax_year:int,investment_income_net:Decimal,capital_gains_net:Decimal)->dict:
    rule=get_savings_rules(jurisdiction,tax_year)
    if rule is None:return {"status":"unsupported_ruleset","jurisdiction":jurisdiction.upper(),"tax_year":tax_year}
    integrated=rule.integrate_current_year(investment_income_net,capital_gains_net)
    return {
        "status":"rule_based","jurisdiction":rule.jurisdiction,"tax_year":tax_year,
        "investment_income_net":str(investment_income_net),"capital_gains_net":str(capital_gains_net),
        "taxable_savings_base":str(integrated.taxable_base),
        "estimated_tax_before_personal_minimum_adjustment":str(rule.tax_for_base(integrated.taxable_base)),
        "offset_from_investment_income":str(integrated.offset_from_investment_income),
        "offset_from_capital_gains":str(integrated.offset_from_capital_gains),
        "carryforward_investment_income":str(integrated.carryforward_investment_income),
        "carryforward_capital_gains":str(integrated.carryforward_capital_gains),
        **_rule_payload(rule),
        "notice":"Integra los dos saldos corrientes del ahorro. No consume pérdidas de años anteriores ni sustituye la declaración oficial.",
    }
