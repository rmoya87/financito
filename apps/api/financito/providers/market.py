from __future__ import annotations
from decimal import Decimal
import csv
from io import StringIO
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
        if not series:
            raise RuntimeError(data.get("Information") or data.get("Note") or "No daily prices returned")
        return [{"date":d,"close":v["4. close"]} for d,v in sorted(series.items())]


class StooqProvider:
    """Free delayed/EOD fallback for common exchange tickers.

    Alpha Vantage remains the preferred provider when configured. Stooq keeps
    basic quote/simulation workflows usable without a paid service or API key.
    """
    BASE="https://stooq.com/q"

    @staticmethod
    def normalize_symbol(symbol:str)->str:
        raw=symbol.strip().lower()
        if not raw:
            raise RuntimeError("Ticker vacío")
        # Stooq uses market suffixes. Bare tickers entered in Financito are
        # overwhelmingly US symbols (AAPL, MSFT, SPY...). Keep explicit
        # suffixes untouched and map bare symbols to the US market.
        return raw if "." in raw else raw+".us"

    def quote(self,symbol:str)->dict:
        normalized=self.normalize_symbol(symbol)
        with httpx.Client(timeout=15,headers={"User-Agent":"Financito/1.0"}) as client:
            response=client.get(
                self.BASE+"/l/",
                params={"s":normalized,"f":"sd2t2ohlcv","h":"","e":"csv"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise RuntimeError(
                        f"Stooq no encontró el ticker {normalized.upper()}. Revisa el símbolo; por ejemplo, Apple es AAPL."
                    ) from None
                raise RuntimeError(f"Stooq no disponible (HTTP {exc.response.status_code})") from None
        rows=list(csv.DictReader(StringIO(response.text)))
        if not rows:
            raise RuntimeError("Stooq no devolvió cotización")
        row=rows[0]
        close=(row.get("Close") or "").strip()
        if not close or close.upper() in {"N/D","N/A","NA","-"}:
            raise RuntimeError("Stooq no dispone de cotización para este ticker")
        day=(row.get("Date") or "").strip()
        time=(row.get("Time") or "").strip()
        as_of=(day+("T"+time if time else "")).strip() or None
        return {
            "symbol":symbol.upper(),
            "price":str(Decimal(close)),
            "provider":"stooq",
            "as_of":as_of,
            "delayed":True,
        }

    def daily(self,symbol:str)->list[dict]:
        normalized=self.normalize_symbol(symbol)
        with httpx.Client(timeout=20,headers={"User-Agent":"Financito/1.0"}) as client:
            response=client.get(self.BASE+"/d/l/",params={"s":normalized,"i":"d"})
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise RuntimeError(
                        f"Stooq no encontró histórico para {normalized.upper()}. Revisa el ticker introducido."
                    ) from None
                raise RuntimeError(f"Stooq no disponible (HTTP {exc.response.status_code})") from None
        rows=[]
        for row in csv.DictReader(StringIO(response.text)):
            day=(row.get("Date") or "").strip()
            close=(row.get("Close") or "").strip()
            if not day or not close or close.upper() in {"N/D","N/A","NA","-"}:
                continue
            rows.append({"date":day,"close":close})
        if not rows:
            raise RuntimeError("Stooq no devolvió histórico para este ticker")
        # A compact history is sufficient for charts/risk and keeps local
        # refreshes fast even for securities with decades of data.
        return rows[-400:]


def quote_with_free_fallback(symbol:str)->dict:
    errors=[]
    try:
        return AlphaVantageProvider().quote(symbol)
    except Exception as exc:
        errors.append(str(exc))
    try:
        return StooqProvider().quote(symbol)
    except Exception as exc:
        errors.append(str(exc))
    raise RuntimeError("No se pudo obtener una cotización gratuita. "+" · ".join(x for x in errors if x))
