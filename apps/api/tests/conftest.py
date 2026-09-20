import os
from pathlib import Path

os.environ.setdefault("FINANCITO_DATA_DIR", "/tmp/financito-tests")
os.environ.setdefault("FINANCITO_VAULT_DIR", "/tmp/financito-tests/vault")
os.environ.setdefault("FINANCITO_ALLOW_PLAINTEXT_SQLITE", "1")
Path("/tmp/financito-tests/vault").mkdir(parents=True, exist_ok=True)

import pytest

@pytest.fixture(scope="session", autouse=True)
def init_schema():
    from financito.migrations import migrate
    migrate()
