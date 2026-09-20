from __future__ import annotations
from datetime import datetime,timezone,timedelta
import hashlib
from sqlalchemy import delete,func,select,text
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Document,ExtractedFact
from ..models_extended import BackupRecord,DocumentChunk,RepairIssue
from .rag import index_document_chunks

def scan(session:Session)->list[RepairIssue]:
    session.execute(delete(RepairIssue).where(RepairIssue.status=="open"))
    issues=[]
    docs=session.scalars(select(Document)).all()
    for d in docs:
        count=session.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id==d.id)) or 0
        if d.extracted_text and count==0:issues.append(RepairIssue(issue_type="missing_document_index",entity_type="document",entity_id=d.id,severity="high",repair_action="reindex_document"))
        try:
            if hashlib.sha256(open(d.file_path,"rb").read()).hexdigest()!=d.sha256:issues.append(RepairIssue(issue_type="vault_hash_mismatch",entity_type="document",entity_id=d.id,severity="critical",repair_action="review_source"))
        except OSError:issues.append(RepairIssue(issue_type="missing_vault_file",entity_type="document",entity_id=d.id,severity="critical",repair_action="review_source"))
    unverified=session.scalar(select(func.count()).select_from(ExtractedFact).where(ExtractedFact.status=="inferred",ExtractedFact.user_verified.is_(False))) or 0
    if unverified:issues.append(RepairIssue(issue_type="unverified_evidence",entity_type="extracted_fact",severity="medium",repair_action="review_evidence",metadata_json=f'{{"count":{unverified}}}'))
    last=session.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc()))
    now=datetime.now(timezone.utc)
    if not last or (last.created_at.replace(tzinfo=timezone.utc) if last.created_at.tzinfo is None else last.created_at)<now-timedelta(days=30):issues.append(RepairIssue(issue_type="backup_stale",severity="high",repair_action="create_backup"))
    session.add_all(issues);session.flush();return issues

def repair(session:Session,issue_id:str)->dict:
    issue=session.get(RepairIssue,issue_id)
    if not issue:raise ValueError("Repair issue not found")
    if issue.repair_action=="reindex_document" and issue.entity_id:
        doc=session.get(Document,issue.entity_id);count=index_document_chunks(session,doc);issue.status="resolved";return {"reindexed_chunks":count}
    if issue.repair_action in {"review_source","review_evidence","create_backup"}:return {"requires_user_action":True,"action":issue.repair_action}
    raise ValueError("Unsupported repair action")
