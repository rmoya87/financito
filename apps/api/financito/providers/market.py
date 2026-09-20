from __future__ import annotations
from decimal import Decimal
import httpx

from ..services.secure_config import get_secret

class AlphaVantageProvider:
    BASE="https://www.alphavantage.co/query"
    def __init__(self,api_key:str|None=None):
        self.key=api_key or get_secret("alpha_vantage_api_key")
        if not self.key:
            raise RuntimeError("Alpha Vantage free API key is not configured")
    def quote(self,symbol:str)->dict:
        with httpx.Client(timeout=15) as c:
            r=c.get(self.BASE,params={"function":"GLOBAL_QUOTE","symbol":symbol,"apikey":self.key});r.raise_for_status();data=r.json()
        q=data.get("Global Quote",{})
        if not q.get("05. price"):
            raise RuntimeError(data.get("Information") or data.get("Note") or "No quote returned")
        return {"symbol":symbol.upper(),"price":str(Decimal(q["05. price"])),"provider":"alpha_vantage","as_of":q.get("07. latest trading day"),"delayed":True}
    def daily(self,symbol:str)->list[dict]:
        with httpx.Client(timeout=20) as c:
            r=c.get(self.BASE,params={"function":"TIME_SERIES_DAILY","symbol":symbol,"outputsize":"compact","apikey":self.key});r.raise_for_status();data=r.json()
        series=data.get("Time Series (Daily)",{})
        return [{"date":d,"close":v["4. close"]} for d,v in sorted(series.items())]
