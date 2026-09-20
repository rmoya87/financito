from __future__ import annotations
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from ..models import Document,ExtractedFact,Transaction
from ..models_extended import RepairIssue
def reconciliation(session:Session)->list[dict]:
    items=[]
    unc=session.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id.is_(None))) or 0
    if unc:items.append({"type":"uncategorized_transactions","count":unc,"severity":"medium"})
    low=session.scalar(select(func.count()).select_from(Transaction).where(Transaction.categorization_confidence<0.5,Transaction.user_verified.is_(False))) or 0
    if low:items.append({"type":"low_confidence_transactions","count":low,"severity":"medium"})
    facts=session.scalar(select(func.count()).select_from(ExtractedFact).where(ExtractedFact.status.in_(["ambiguous","conflicting"]))) or 0
    if facts:items.append({"type":"contract_evidence_conflicts","count":facts,"severity":"high"})
    failed=session.scalar(select(func.count()).select_from(Document).where(Document.status=="failed")) or 0
    if failed:items.append({"type":"failed_documents","count":failed,"severity":"high"})
    return items
