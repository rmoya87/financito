from __future__ import annotations
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev

def returns(prices:list[float])->list[float]:
    return [prices[i]/prices[i-1]-1 for i in range(1,len(prices)) if prices[i-1]!=0]

def max_drawdown(prices:list[float])->float:
    if not prices:return 0.0
    peak=prices[0];worst=0.0
    for p in prices:
        peak=max(peak,p)
        if peak:worst=min(worst,p/peak-1)
    return worst

def risk_metrics(prices:list[float],periods_per_year:int=252,risk_free_rate:float=0.0)->dict:
    r=returns(prices)
    if len(r)<2:return {"sample_count":len(r),"volatility":None,"sharpe":None,"sortino":None,"max_drawdown":max_drawdown(prices)}
    avg=mean(r);vol=pstdev(r)*sqrt(periods_per_year);rf=risk_free_rate/periods_per_year
    sharpe=None if vol==0 else (avg-rf)*periods_per_year/vol
    downside=[x for x in r if x<0];down=pstdev(downside)*sqrt(periods_per_year) if len(downside)>1 else 0
    sortino=None if down==0 else (avg-rf)*periods_per_year/down
    sorted_r=sorted(r);idx=max(0,int(len(sorted_r)*0.05)-1);var95=sorted_r[idx];tail=[x for x in sorted_r if x<=var95];cvar95=mean(tail) if tail else var95
    return {"sample_count":len(r),"volatility":vol,"sharpe":sharpe,"sortino":sortino,"max_drawdown":max_drawdown(prices),"var_95":var95,"cvar_95":cvar95}
