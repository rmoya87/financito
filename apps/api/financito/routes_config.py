from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session

from .db import SessionLocal
from .services.banking import close_connection,complete_authorization,list_connections,sync_connection
from .services.secure_config import provider_status,set_secret

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

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
