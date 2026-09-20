from sqlalchemy import text
from financito.db import engine
from financito.migrations import MIGRATION_VERSION, migrate

def test_migration_is_idempotent():
    assert migrate() == MIGRATION_VERSION
    assert migrate() == MIGRATION_VERSION
    with engine.connect() as conn:
        assert conn.execute(text("SELECT MAX(version) FROM financito_schema_version")).scalar_one() == MIGRATION_VERSION
