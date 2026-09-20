from __future__ import annotations
from datetime import date,timedelta
from decimal import Decimal
from sqlalchemy import delete,select
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


def scan_coverage_overlaps(session:Session)->list[CoverageOverlap]:
    session.execute(delete(CoverageOverlap).where(CoverageOverlap.status=="review"))
    facts=session.scalars(select(CoverageFact).where(CoverageFact.user_verified.is_(True))).all()
    created=[]
    for i,left in enumerate(facts):
        for right in facts[i+1:]:
            if left.coverage_type.strip().lower()!=right.coverage_type.strip().lower():continue
            if left.insurance_policy_id and right.insurance_policy_id and left.insurance_policy_id==right.insurance_policy_id:continue
            if left.contract_id and right.contract_id and left.contract_id==right.contract_id:continue
            starts=[d for d in (left.effective_from,right.effective_from) if d]
            ends=[d for d in (left.effective_to,right.effective_to) if d]
            if starts and ends and max(starts)>min(ends):continue
            overlap_type="duplicate_verified"
            if left.limit_amount is None or right.limit_amount is None:overlap_type="duplicate_unknown_limit"
            row=CoverageOverlap(coverage_type=left.coverage_type,left_coverage_fact_id=left.id,right_coverage_fact_id=right.id,overlap_type=overlap_type,estimated_redundant_cost=None,confidence=Decimal("0.90"),status="review")
            session.add(row);created.append(row)
    session.flush();return created
