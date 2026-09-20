from pathlib import Path
from financito.config import settings
from financito.services.backup import create_backup, stage_restore

def test_encrypted_backup_roundtrip_stages_restore():
    destination=settings.data_dir/"test.financito-backup"
    result=create_backup("correct horse battery staple",str(destination))
    assert destination.exists()
    assert result["size"] > 0
    staged=stage_restore("correct horse battery staple",str(destination))
    assert staged["verified"] is True
    assert staged["restart_required"] is True
    (settings.data_dir/".restore-pending").unlink(missing_ok=True)
