from __future__ import annotations
from sqlalchemy import text
from .db import Base,engine
MIGRATION_VERSION=2

def _fts(conn):
    conn.execute(text("""CREATE VIRTUAL TABLE IF NOT EXISTS document_chunk_fts USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, text, heading, section, tokenize='unicode61 remove_diacritics 2')"""))

def migrate()->int:
    from . import models,models_extended
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS financito_schema_version (version INTEGER NOT NULL)"))
        current=conn.execute(text("SELECT MAX(version) FROM financito_schema_version")).scalar()
        if current is not None and current>MIGRATION_VERSION: raise RuntimeError(f"Database schema {current} is newer than application schema {MIGRATION_VERSION}")
        Base.metadata.create_all(bind=conn);_fts(conn)
        current=int(current or 0)
        if current<MIGRATION_VERSION:
            conn.execute(text("INSERT INTO financito_schema_version(version) VALUES (:v)"),{"v":MIGRATION_VERSION})
        return MIGRATION_VERSION
