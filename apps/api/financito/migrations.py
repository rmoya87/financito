from __future__ import annotations

from sqlalchemy import text
from .db import Base, engine

MIGRATION_VERSION = 1


def migrate() -> int:
    """Apply the versioned baseline schema without destructive rebuilds.

    Future schema changes must append explicit migration functions before
    incrementing MIGRATION_VERSION. This baseline is intentionally equivalent
    to an initial Alembic revision while keeping the first launcher dependency-light.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS financito_schema_version (version INTEGER NOT NULL)"))
        current = conn.execute(text("SELECT MAX(version) FROM financito_schema_version")).scalar()
        if current is None:
            Base.metadata.create_all(bind=conn)
            conn.execute(text("INSERT INTO financito_schema_version(version) VALUES (:v)"), {"v": MIGRATION_VERSION})
            return MIGRATION_VERSION
        if current > MIGRATION_VERSION:
            raise RuntimeError(f"Database schema {current} is newer than application schema {MIGRATION_VERSION}")
        return int(current)
