from __future__ import annotations
from decimal import Decimal,ROUND_HALF_UP
Q=Decimal("0.01")
def money(v:Decimal)->Decimal:return v.quantize(Q,rounding=ROUND_HALF_UP)
def run_stress(liquidity:Decimal,monthly_income:Decimal,monthly_expenses:Decimal,portfolio_value:Decimal,income_reduction_pct:Decimal,extraordinary_expense:Decimal,portfolio_drop_pct:Decimal,months:int)->dict:
    reduced_income=monthly_income*(Decimal("1")-income_reduction_pct/Decimal("100"))
    monthly_net=reduced_income-monthly_expenses
    ending_liquidity=liquidity-extraordinary_expense+monthly_net*months
    burn=max(Decimal("0"),monthly_expenses-reduced_income)
    runway=None if burn==0 else max(Decimal("0"),(liquidity-extraordinary_expense)/burn)
    stressed_portfolio=portfolio_value*(Decimal("1")-portfolio_drop_pct/Decimal("100"))
    return {"monthly_income_after_shock":str(money(reduced_income)),"monthly_net":str(money(monthly_net)),"ending_liquidity":str(money(ending_liquidity)),"cash_runway_months":None if runway is None else str(runway.quantize(Decimal("0.1"))),"portfolio_after_shock":str(money(stressed_portfolio)),"assumptions":{"income_reduction_pct":str(income_reduction_pct),"extraordinary_expense":str(extraordinary_expense),"portfolio_drop_pct":str(portfolio_drop_pct),"months":months}}
