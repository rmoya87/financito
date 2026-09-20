from __future__ import annotations
import os
from datetime import datetime
import httpx

BASE="https://data.sec.gov"

class SecFundamentalsProvider:
    def __init__(self,user_agent:str|None=None):
        self.user_agent=user_agent or os.getenv("FINANCITO_SEC_USER_AGENT","")
        if not self.user_agent:
            raise RuntimeError("Configure FINANCITO_SEC_USER_AGENT with an identifying contact string")
    def companyfacts(self,cik:str)->dict:
        normalized=str(cik).strip().lstrip("0").zfill(10)
        with httpx.Client(base_url=BASE,timeout=25,headers={"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate","Accept":"application/json"}) as client:
            r=client.get(f"/api/xbrl/companyfacts/CIK{normalized}.json");r.raise_for_status();return r.json()
    @staticmethod
    def latest_us_gaap(data:dict,concepts:list[str])->dict:
        facts=data.get("facts",{}).get("us-gaap",{});out={}
        for concept in concepts:
            node=facts.get(concept,{})
            units=node.get("units",{})
            candidates=[]
            for unit,rows in units.items():
                for row in rows:
                    if row.get("val") is not None and row.get("filed"):
                        candidates.append((row.get("filed"),unit,row))
            if candidates:
                _,unit,row=max(candidates,key=lambda x:x[0])
                out[concept]={"value":row["val"],"unit":unit,"period_end":row.get("end"),"filed":row.get("filed"),"form":row.get("form"),"accession":row.get("accn")}
        return out
