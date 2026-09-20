from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Account,Document,Transaction
from .services.privacy import erase_all_application_data,rebuild_derived

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

class EraseIn(BaseModel):
    confirmation:str
    clear_provider_secrets:bool=True

@router.get("/privacy/summary")
def privacy_summary(db:Session=Depends(dbdep)):
    return {
        "accounts":db.scalar(select(func.count()).select_from(Account)) or 0,
        "transactions":db.scalar(select(func.count()).select_from(Transaction)) or 0,
        "documents":db.scalar(select(func.count()).select_from(Document)) or 0,
        "vault_originals_managed":False,
    }

@router.post("/privacy/rebuild-derived")
def privacy_rebuild(db:Session=Depends(dbdep)):
    try:
        result=rebuild_derived(db);db.commit();return result
    except Exception as exc:
        db.rollback();raise HTTPException(500,f"Could not rebuild derived data: {exc}")

@router.delete("/privacy/data")
def privacy_erase(payload:EraseIn,db:Session=Depends(dbdep)):
    if payload.confirmation!="BORRAR FINANCITO":
        raise HTTPException(400,'Type exactly "BORRAR FINANCITO" to confirm')
    try:
        result=erase_all_application_data(db,payload.clear_provider_secrets);db.commit();return result
    except Exception as exc:
        db.rollback();raise HTTPException(500,f"Could not erase application data: {exc}")
