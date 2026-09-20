import pytest
from financito.config import settings
from financito.services.documents import safe_path

def test_vault_accepts_inside_and_rejects_outside():
    inside=settings.vault_dir/"inside.txt"; inside.write_text("ok"); assert safe_path(inside)==inside.resolve()
    outside=settings.data_dir.parent/"financito-outside-test.txt"; outside.write_text("secret")
    try:
        with pytest.raises(ValueError): safe_path(outside)
    finally: outside.unlink(missing_ok=True)
