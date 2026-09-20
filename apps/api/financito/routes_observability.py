from __future__ import annotations

from datetime import date
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session

from .db import SessionLocal
from .services.developer import snapshot
from .services.temporal import wealth_as_of

router=APIRouter(prefix="/api/v1")

def dbdep():
    s=SessionLocal()
    try:yield s
    finally:s.close()

@router.get("/developer/snapshot")
def developer_snapshot(db:Session=Depends(dbdep)):
    return snapshot(db)

@router.get("/temporal/wealth")
def temporal_wealth(as_of:date,db:Session=Depends(dbdep)):
    try:return wealth_as_of(db,as_of)
    except ValueError as exc:raise HTTPException(400,str(exc))
