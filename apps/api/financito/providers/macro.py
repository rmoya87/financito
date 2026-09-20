from __future__ import annotations
import csv
from io import StringIO
import httpx

BASE="https://data-api.ecb.europa.eu/service"

class EcbMacroProvider:
    def series(self,flow:str,key:str,start:str|None=None,end:str|None=None,last_n:int|None=None)->list[dict]:
        params={"format":"csvdata","detail":"dataonly"}
        if start:params["startPeriod"]=start
        if end:params["endPeriod"]=end
        if last_n is not None:params["lastNObservations"]=str(last_n)
        with httpx.Client(base_url=BASE,timeout=30,headers={"Accept":"text/csv"}) as client:
            r=client.get(f"/data/{flow}/{key}",params=params);r.raise_for_status()
        rows=list(csv.DictReader(StringIO(r.text)))
        return rows
    def fx(self,currency:str,frequency:str="D",last_n:int=30)->list[dict]:
        return self.series("EXR",f"{frequency}.{currency.upper()}.EUR.SP00.A",last_n=last_n)
