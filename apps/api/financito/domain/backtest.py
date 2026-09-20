from __future__ import annotations
from math import sqrt
from statistics import mean,pstdev

def backtest_ma(prices:list[float],short:int=20,long:int=60,fee_bps:float=5.0)->dict:
    if short<=0 or long<=short or len(prices)<=long:raise ValueError("Insufficient price history or invalid windows")
    equity=1.0;benchmark=prices[-1]/prices[long];prev_signal=0;curve=[]
    daily=[]
    for i in range(long,len(prices)):
        s=mean(prices[i-short:i]);l=mean(prices[i-long:i]);signal=1 if s>l else 0
        ret=prices[i]/prices[i-1]-1
        turnover=abs(signal-prev_signal)
        strategy=signal*ret-turnover*(fee_bps/10000);equity*=1+strategy;daily.append(strategy);curve.append(equity);prev_signal=signal
    peak=1.0;dd=0.0
    for x in curve:peak=max(peak,x);dd=min(dd,x/peak-1)
    vol=pstdev(daily)*sqrt(252) if len(daily)>1 else 0;sharpe=(mean(daily)*252/vol) if vol else None
    years=max(1/252,len(daily)/252);cagr=equity**(1/years)-1
    return {"final_value":equity,"benchmark_value":benchmark,"cagr":cagr,"volatility":vol,"sharpe":sharpe,"max_drawdown":dd,"observations":len(daily),"assumptions":{"short_window":short,"long_window":long,"fee_bps":fee_bps}}
def amortize_vs_invest(principal:float,debt_rate:float,investment_return:float,horizon_years:int,tax_rate:float=0.0)->dict:
    debt_saved=principal*((1+debt_rate)**horizon_years-1);gross=principal*((1+investment_return)**horizon_years-1);investment_gain=gross*(1-tax_rate)
    return {"debt_interest_avoided":debt_saved,"investment_gain_after_assumed_tax":investment_gain,"difference_invest_minus_amortize":investment_gain-debt_saved,"assumptions":{"principal":principal,"debt_rate":debt_rate,"investment_return":investment_return,"horizon_years":horizon_years,"tax_rate":tax_rate},"notice":"Escenario, no predicción. La rentabilidad de inversión es una hipótesis explícita."}
