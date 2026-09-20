from __future__ import annotations

from datetime import datetime,timezone,timedelta
from pathlib import Path
import os

import httpx
import jwt

from ..services.secure_config import get_secret

BASE="https://api.enablebanking.com"

class EnableBankingProvider:
    def __init__(self,app_id:str|None=None,private_key:str|None=None,private_key_path:str|None=None):
        self.app_id=app_id or get_secret("enable_banking_app_id") or os.getenv("FINANCITO_ENABLE_BANKING_APP_ID","")
        pem=private_key or get_secret("enable_banking_private_key")
        legacy_path=private_key_path or os.getenv("FINANCITO_ENABLE_BANKING_PRIVATE_KEY","")
        if not pem and legacy_path:
            pem=Path(legacy_path).expanduser().read_text(encoding="utf-8")
        if not self.app_id or not pem:
            raise RuntimeError("Enable Banking credentials are not configured")
        self.private_key=pem

    def token(self)->str:
        now=datetime.now(timezone.utc)
        payload={
            "iss":"enablebanking.com",
            "aud":"api.enablebanking.com",
            "iat":int(now.timestamp()),
            "exp":int((now+timedelta(minutes=55)).timestamp()),
        }
        return jwt.encode(payload,self.private_key,algorithm="RS256",headers={"kid":self.app_id})

    def _headers(self)->dict:
        return {"Authorization":f"Bearer {self.token()}","Accept":"application/json"}

    def _get(self,path:str,params:dict|None=None)->dict:
        with httpx.Client(base_url=BASE,timeout=25,headers=self._headers()) as client:
            r=client.get(path,params=params);r.raise_for_status();return r.json()

    def _post(self,path:str,body:dict)->dict:
        with httpx.Client(base_url=BASE,timeout=30,headers={**self._headers(),"Content-Type":"application/json"}) as client:
            r=client.post(path,json=body);r.raise_for_status();return r.json()

    def _delete(self,path:str)->dict:
        with httpx.Client(base_url=BASE,timeout=25,headers=self._headers()) as client:
            r=client.delete(path);r.raise_for_status()
            return r.json() if r.content else {"message":"OK"}

    def application(self)->dict:
        return self._get("/application")

    def aspsps(self,country:str="ES")->dict:
        return self._get("/aspsps",{"country":country})

    def start_authorization(self,bank_name:str,country:str,redirect_url:str,state:str,valid_until:str,psu_type:str="personal")->dict:
        return self._post("/auth",{
            "access":{"valid_until":valid_until},
            "aspsp":{"name":bank_name,"country":country},
            "state":state,
            "redirect_url":redirect_url,
            "psu_type":psu_type,
        })

    def authorize_session(self,code:str)->dict:
        return self._post("/sessions",{"code":code})

    def session(self,session_id:str)->dict:
        return self._get(f"/sessions/{session_id}")

    def close_session(self,session_id:str)->dict:
        return self._delete(f"/sessions/{session_id}")

    def account_details(self,account_id:str)->dict:
        return self._get(f"/accounts/{account_id}/details")

    def balances(self,account_id:str)->dict:
        return self._get(f"/accounts/{account_id}/balances")

    def transactions(self,account_id:str,date_from:str|None=None,date_to:str|None=None,continuation_key:str|None=None)->dict:
        params={k:v for k,v in {
            "date_from":date_from,
            "date_to":date_to,
            "continuation_key":continuation_key,
        }.items() if v}
        return self._get(f"/accounts/{account_id}/transactions",params)
