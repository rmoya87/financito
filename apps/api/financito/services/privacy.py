from __future__ import annotations

from sqlalchemy import delete,text
from sqlalchemy.orm import Session

from ..db import Base
from ..models import Document
from ..models_extended import DocumentChunk,MarketPrice,NewsItem,RepairIssue
from ..models_analytics import Anomaly,CryptoSnapshot,FundamentalSnapshot,RecurringSeries
from .documents import reprocess_document
from .transaction_ops import detect_internal_transfers,detect_refunds
from ..domain.analytics import detect_anomalies,detect_recurring
from .repair import scan
from .secure_config import clear_all_secrets

DERIVED_MODELS=(DocumentChunk,Anomaly,RecurringSeries,RepairIssue,MarketPrice,NewsItem,FundamentalSnapshot,CryptoSnapshot)

def _clear_vector_tables(session:Session)->None:
    names=session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'document_chunk_vec_%'")).scalars().all()
    for name in names:
        safe="".join(ch for ch in name if ch.isalnum() or ch=="_")
        if safe==name:
            session.execute(text(f'DELETE FROM "{safe}"'))

def rebuild_derived(session:Session)->dict:
    # Preserve source records and user-verified evidence. Rebuild indexes and analytical derivatives.
    session.execute(text("DELETE FROM document_chunk_fts"))
    _clear_vector_tables(session)
    session.execute(delete(DocumentChunk))
    session.execute(delete(Anomaly))
    session.execute(delete(RecurringSeries))
    session.execute(delete(RepairIssue))
    docs=session.query(Document).all()
    chunks=0
    facts=0
    for doc in docs:
        result=reprocess_document(session,doc)
        chunks+=result.chunks_created
        facts+=result.facts_created
    transfers=detect_internal_transfers(session)
    refunds=detect_refunds(session)
    recurring=len(detect_recurring(session))
    anomalies=len(detect_anomalies(session))
    issues=len(scan(session))
    session.flush()
    return {
        "documents":len(docs),
        "chunks":chunks,
        "new_inferred_facts":facts,
        "transfer_pairs":transfers,
        "refunds":refunds,
        "recurring_series":recurring,
        "anomalies":anomalies,
        "repair_issues":issues,
    }

def erase_all_application_data(session:Session,clear_secrets:bool=True)->dict:
    session.execute(text("DELETE FROM document_chunk_fts"))
    _clear_vector_tables(session)
    # Reverse dependency order preserves FK constraints.
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.flush()
    cleared=clear_all_secrets() if clear_secrets else []
    return {"database_rows_removed":True,"provider_secrets_cleared":cleared,"vault_originals_deleted":False}
