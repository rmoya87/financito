from __future__ import annotations

from datetime import date,datetime,timezone
from pathlib import Path

from sqlalchemy import func,select
from sqlalchemy.orm import Session

from ..config import settings
from ..migrations import MIGRATION_VERSION
from ..models import Account,DecisionCase,Document,ExtractedFact,Transaction
from ..models_extended import DocumentChunk,MarketPrice,NewsItem,RepairIssue
from ..models_analytics import BankingAccountLink,BankingConnection
from .local_ai import status as ai_status
from .secure_config import provider_status


def _aware(value:datetime|None)->datetime|None:
    if value is None:return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _freshness(value:datetime|date|None,max_hours:int|None)->dict:
    if value is None:return {"value":None,"age_hours":None,"status":"unknown"}
    if isinstance(value,date) and not isinstance(value,datetime):
        moment=datetime.combine(value,datetime.min.time(),tzinfo=timezone.utc)
    else:
        moment=_aware(value)
    age=max(0,(datetime.now(timezone.utc)-moment).total_seconds()/3600)
    status="observed" if max_hours is None else ("fresh" if age<=max_hours else "stale")
    return {"value":value,"age_hours":round(age,2),"status":status}


def _vault_stats()->dict:
    root=settings.vault_dir
    if not root.exists():return {"files":0,"bytes":0}
    files=0;size=0
    for item in root.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                files+=1;size+=item.stat().st_size
        except OSError:
            continue
    return {"files":files,"bytes":size}


def snapshot(session:Session)->dict:
    latest_tx=session.scalar(select(func.max(Transaction.booking_date)))
    latest_doc=session.scalar(select(func.max(Document.updated_at)))
    latest_bank=session.scalar(select(func.max(BankingAccountLink.last_sync_at)))
    latest_market=session.scalar(select(func.max(MarketPrice.fetched_at)))
    latest_news=session.scalar(select(func.max(NewsItem.fetched_at)))
    counts={
        "accounts":session.scalar(select(func.count()).select_from(Account)) or 0,
        "transactions":session.scalar(select(func.count()).select_from(Transaction)) or 0,
        "documents":session.scalar(select(func.count()).select_from(Document)) or 0,
        "document_chunks":session.scalar(select(func.count()).select_from(DocumentChunk)) or 0,
        "verified_facts":session.scalar(select(func.count()).select_from(ExtractedFact).where(ExtractedFact.user_verified.is_(True))) or 0,
        "bank_connections":session.scalar(select(func.count()).select_from(BankingConnection)) or 0,
        "market_prices":session.scalar(select(func.count()).select_from(MarketPrice)) or 0,
        "news_items":session.scalar(select(func.count()).select_from(NewsItem)) or 0,
        "decisions":session.scalar(select(func.count()).select_from(DecisionCase)) or 0,
        "repair_issues":session.scalar(select(func.count()).select_from(RepairIssue).where(RepairIssue.status=="open")) or 0,
    }
    try:db_bytes=settings.db_path.stat().st_size
    except OSError:db_bytes=0
    return {
        "schema_version":MIGRATION_VERSION,
        "runtime":{"local_only":True,"database_encrypted":not settings.allow_plaintext_sqlite,"db_bytes":db_bytes,"vault":_vault_stats()},
        "counts":counts,
        "freshness":{
            "transactions":_freshness(latest_tx,None),
            "documents":_freshness(latest_doc,None),
            "banking":_freshness(latest_bank,48),
            "market":_freshness(latest_market,48),
            "news":_freshness(latest_news,48),
        },
        "ai":ai_status(),
        "providers":provider_status(),
        "provenance":{
            "banking":"Enable Banking -> normalized local Account/Transaction",
            "market":"Alpha Vantage observations persisted in market_price",
            "crypto":"CoinGecko queried on demand; derived risk calculated locally",
            "fundamentals":"SEC EDGAR companyfacts queried on demand",
            "macro":"ECB SDMX queried on demand",
            "news":"GDELT search/ingest with local canonical URL dedupe",
            "documents":"Vault file -> extraction/OCR -> facts/chunks -> FTS/vector",
        },
    }
