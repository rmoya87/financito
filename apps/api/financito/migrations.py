from __future__ import annotations
from sqlalchemy import inspect,text
from .db import Base,engine
MIGRATION_VERSION=15

def _fts(conn):
    conn.execute(text("""CREATE VIRTUAL TABLE IF NOT EXISTS document_chunk_fts USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, text, heading, section, tokenize='unicode61 remove_diacritics 2')"""))

def _add_nullable_column(conn,table:str,column:str,ddl:str)->None:
    columns={item["name"] for item in inspect(conn).get_columns(table)}
    if column in columns:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

def _account_link_columns(conn)->None:
    for table in ("mortgage","portfolio","financial_goal","insurance_policy","commitment"):
        _add_nullable_column(conn,table,"account_id","VARCHAR(36)")
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_account_id ON {table} (account_id)"))

def migrate()->int:
    from . import models,models_extended,models_analytics
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS financito_schema_version (version INTEGER NOT NULL)"))
        current=conn.execute(text("SELECT MAX(version) FROM financito_schema_version")).scalar()
        if current is not None and current>MIGRATION_VERSION:
            raise RuntimeError(f"Database schema {current} is newer than application schema {MIGRATION_VERSION}")
        Base.metadata.create_all(bind=conn)
        _account_link_columns(conn)
        _add_nullable_column(conn,"budget","account_id","VARCHAR(36)")
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_budget_account_id ON budget (account_id)"))
        _add_nullable_column(conn,"financial_goal","allocated_amount","NUMERIC(18,4) NOT NULL DEFAULT 0")
        _add_nullable_column(conn,"financial_goal","emergency_months_target","INTEGER")
        _fts(conn)
        current=int(current or 0)
        if current<MIGRATION_VERSION:
            conn.execute(text("INSERT INTO financito_schema_version(version) VALUES (:v)"),{"v":MIGRATION_VERSION})
        return MIGRATION_VERSION
