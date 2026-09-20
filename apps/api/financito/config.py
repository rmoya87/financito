from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, secrets

@dataclass(frozen=True)
class Settings:
    data_dir:Path; db_path:Path; vault_dir:Path; frontend_dir:Path; backup_dir:Path
    host:str; port:int; allow_plaintext_sqlite:bool
    local_ai_url:str; local_ai_model:str; embedding_model:str
    session_secret:str
    @classmethod
    def from_env(cls)->"Settings":
        root=Path(os.getenv("FINANCITO_DATA_DIR",Path.home()/".financito")).expanduser().resolve()
        vault=Path(os.getenv("FINANCITO_VAULT_DIR",root/"vault")).expanduser().resolve()
        frontend=Path(os.getenv("FINANCITO_FRONTEND_DIR",Path(__file__).parents[3]/"web"/"out")).expanduser().resolve()
        backup=Path(os.getenv("FINANCITO_BACKUP_DIR",root/"backups")).expanduser().resolve()
        for p in (root,vault,backup):p.mkdir(parents=True,exist_ok=True)
        return cls(root,Path(os.getenv("FINANCITO_DB_PATH",root/"financito.db")).expanduser().resolve(),vault,frontend,backup,os.getenv("FINANCITO_HOST","127.0.0.1"),int(os.getenv("FINANCITO_PORT","8765")),os.getenv("FINANCITO_ALLOW_PLAINTEXT_SQLITE","0")=="1",os.getenv("FINANCITO_LOCAL_AI_URL","http://127.0.0.1:11434"),os.getenv("FINANCITO_LOCAL_AI_MODEL",""),os.getenv("FINANCITO_EMBEDDING_MODEL","embeddinggemma"),os.getenv("FINANCITO_SESSION_SECRET",secrets.token_urlsafe(32)))
settings=Settings.from_env()
