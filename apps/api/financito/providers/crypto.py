from __future__ import annotations
import os
import httpx

BASE="https://api.coingecko.com/api/v3"

class CoinGeckoDemoProvider:
    def __init__(self,api_key:str|None=None):
        self.api_key=api_key or os.getenv("FINANCITO_COINGECKO_DEMO_KEY","")
    def _headers(self)->dict:
        return {"x-cg-demo-api-key":self.api_key} if self.api_key else {}
    def simple_price(self,ids:list[str],vs_currency:str="eur")->dict:
        with httpx.Client(base_url=BASE,timeout=20,headers=self._headers()) as client:
            r=client.get("/simple/price",params={"ids":",".join(ids),"vs_currencies":vs_currency,"include_market_cap":"true","include_24hr_vol":"true","include_24hr_change":"true","include_last_updated_at":"true"});r.raise_for_status();return r.json()
    def market_chart(self,coin_id:str,vs_currency:str="eur",days:int=30)->dict:
        with httpx.Client(base_url=BASE,timeout=25,headers=self._headers()) as client:
            r=client.get(f"/coins/{coin_id}/market_chart",params={"vs_currency":vs_currency,"days":days});r.raise_for_status();return r.json()
