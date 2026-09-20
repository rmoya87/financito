from sqlalchemy import text
from financito.db import engine
from financito.migrations import migrate

def test_migration_is_idempotent():
    assert migrate()==1 and migrate()==1
    with engine.connect() as conn: assert conn.execute(text("SELECT MAX(version) FROM financito_schema_version")).scalar_one()==1
