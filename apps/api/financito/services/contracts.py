from __future__ import annotations
from datetime import date,timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import ActionItem,Contract
from ..models_extended import CoverageFact,CoverageOverlap

def refresh_contract_actions(session:Session,today:date|None=None)->int:
    today=today or date.today();created=0
    for c in session.scalars(select(Contract)).all():
        if not c.renewal_date:continue
        notice=c.cancellation_notice_days
        due=c.renewal_date-timedelta(days=notice) if notice is not None else c.renewal_date
        if today<=due<=today+timedelta(days=90):
            exists=session.scalar(select(ActionItem.id).where(ActionItem.action_type=="contract_notice",ActionItem.related_entity_id==c.id,ActionItem.status.in_(["pending","in_progress"])))
            if not exists:
                title=f"Revisar renovación de {c.provider_name}"
                if notice is None:title+="; falta confirmar preaviso"
                session.add(ActionItem(action_type="contract_notice",title=title,related_entity_type="contract",related_entity_id=c.id,due_date=due,priority="high",source_type="contract",source_ref=c.id));created+=1
    return created

def compare_coverages(session:Session,left_id:str,right_id:str)->dict:
    left=session.get(CoverageFact,left_id);right=session.get(CoverageFact,right_id)
    if not left or not right:raise ValueError("Coverage not found")
    same=left.coverage_type==right.coverage_type
    comparable=same and left.user_verified and right.user_verified
    overlap="none"
    if comparable:
        if left.limit_amount is None or right.limit_amount is None:overlap="partial_unknown_limit"
        else:overlap="overlap"
    return {"same_type":same,"comparable":comparable,"overlap_type":overlap,"left_limit":None if left.limit_amount is None else str(left.limit_amount),"right_limit":None if right.limit_amount is None else str(right.limit_amount),"warning":None if comparable else "No se considera cobertura equivalente sin hechos verificados."}
