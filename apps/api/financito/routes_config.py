from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session

from .db import SessionLocal
from .services.banking import close_connection,complete_authorization,list_connections,sync_connection
from .services.secure_config import provider_status,set_secret
from .services.preferences import read_preferences,update_preferences
from .services.local_ai import status as ai_status
from .providers.enable_banking import EnableBankingProvider

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

class AIConfigIn(BaseModel):
    local_ai_model:str|None=None
    embedding_model:str|None=None

class ProviderSecretsIn(BaseModel):
    enable_banking_app_id:str|None=None
    enable_banking_private_key:str|None=None
    alpha_vantage_api_key:str|None=None
    coingecko_demo_key:str|None=None
    sec_user_agent:str|None=None

@router.get("/provider-config")
def provider_config():
    return provider_status()

@router.patch("/provider-config")
def update_provider_config(p:ProviderSecretsIn):
    changed=[]
    for name,value in p.model_dump(exclude_unset=True).items():
        try:set_secret(name,value)
        except RuntimeError as exc:raise HTTPException(503,str(exc))
        changed.append(name)
    return {"updated":changed,"status":provider_status()}

@router.get("/banking/aspsps")
def banking_aspsps(country:str="ES"):
    try:
        return EnableBankingProvider().aspsps(country)
    except Exception as exc:
        raise HTTPException(503,str(exc))

@router.post("/banking/auth")
def banking_auth(bank_name:str,country:str,redirect_url:str,state:str,valid_until:str,psu_type:str="personal"):
    try:
        return EnableBankingProvider().start_authorization(bank_name,country,redirect_url,state,valid_until,psu_type)
    except Exception as exc:
        raise HTTPException(503,str(exc))

@router.get("/banking/connections")
def banking_connections(db:Session=Depends(dbdep)):
    return list_connections(db)

@router.post("/banking/complete")
def banking_complete(code:str,db:Session=Depends(dbdep)):
    try:
        result=complete_authorization(db,code);db.commit();return result
    except Exception as exc:
        db.rollback();raise HTTPException(503,str(exc))

@router.post("/banking/connections/{connection_id}/sync")
def banking_sync(connection_id:str,db:Session=Depends(dbdep)):
    try:
        result=sync_connection(db,connection_id);db.commit();return result
    except ValueError as exc:
        db.rollback();raise HTTPException(404,str(exc))
    except Exception as exc:
        db.rollback();raise HTTPException(503,str(exc))

@router.delete("/banking/connections/{connection_id}")
def banking_close(connection_id:str,db:Session=Depends(dbdep)):
    try:
        result=close_connection(db,connection_id);db.commit();return result
    except ValueError as exc:
        db.rollback();raise HTTPException(404,str(exc))
    except Exception as exc:
        db.rollback();raise HTTPException(503,str(exc))


@router.get("/ai/config")
def ai_config():
    return {"preferences":read_preferences(),"status":ai_status()}

@router.patch("/ai/config")
def update_ai_config(p:AIConfigIn):
    values=p.model_dump(exclude_unset=True)
    return {"preferences":update_preferences(values),"status":ai_status()}
