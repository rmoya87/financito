from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
import os
import httpx,jwt
BASE="https://api.enablebanking.com"
class EnableBankingProvider:
    def __init__(self,app_id:str|None=None,private_key_path:str|None=None):
        self.app_id=app_id or os.getenv("FINANCITO_ENABLE_BANKING_APP_ID","")
        self.private_key_path=private_key_path or os.getenv("FINANCITO_ENABLE_BANKING_PRIVATE_KEY","")
        if not self.app_id or not self.private_key_path:raise RuntimeError("Enable Banking credentials are not configured")
        self.private_key=Path(self.private_key_path).expanduser().read_text()
    def token(self)->str:
        now=datetime.now(timezone.utc);payload={"iss":"enablebanking.com","aud":"api.enablebanking.com","iat":int(now.timestamp()),"exp":int((now+timedelta(minutes=55)).timestamp())}
        return jwt.encode(payload,self.private_key,algorithm="RS256",headers={"kid":self.app_id})
    def _get(self,path:str,params:dict|None=None)->dict:
        with httpx.Client(base_url=BASE,timeout=20,headers={"Authorization":f"Bearer {self.token()}","Accept":"application/json"}) as client:
            r=client.get(path,params=params);r.raise_for_status();return r.json()
    def application(self)->dict:return self._get("/application")
    def balances(self,account_id:str)->dict:return self._get(f"/accounts/{account_id}/balances")
    def transactions(self,account_id:str,date_from:str|None=None,date_to:str|None=None,continuation_key:str|None=None)->dict:
        params={k:v for k,v in {"date_from":date_from,"date_to":date_to,"continuation_key":continuation_key}.items() if v}
        return self._get(f"/accounts/{account_id}/transactions",params)
