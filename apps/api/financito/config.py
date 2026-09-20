from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import secrets


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    vault_dir: Path
    frontend_dir: Path
    host: str
    port: int
    allow_plaintext_sqlite: bool
    local_ai_url: str
    local_ai_model: str
    session_secret: str

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.getenv("FINANCITO_DATA_DIR", Path.home() / ".financito")).expanduser().resolve()
        vault = Path(os.getenv("FINANCITO_VAULT_DIR", root / "vault")).expanduser().resolve()
        frontend = Path(os.getenv("FINANCITO_FRONTEND_DIR", Path(__file__).parents[3] / "web" / "out")).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        vault.mkdir(parents=True, exist_ok=True)
        return cls(
            data_dir=root,
            db_path=Path(os.getenv("FINANCITO_DB_PATH", root / "financito.db")).expanduser().resolve(),
            vault_dir=vault,
            frontend_dir=frontend,
            host=os.getenv("FINANCITO_HOST", "127.0.0.1"),
            port=int(os.getenv("FINANCITO_PORT", "8765")),
            allow_plaintext_sqlite=os.getenv("FINANCITO_ALLOW_PLAINTEXT_SQLITE", "0") == "1",
            local_ai_url=os.getenv("FINANCITO_LOCAL_AI_URL", "http://127.0.0.1:11434"),
            local_ai_model=os.getenv("FINANCITO_LOCAL_AI_MODEL", ""),
            session_secret=os.getenv("FINANCITO_SESSION_SECRET", secrets.token_urlsafe(32)),
        )


settings = Settings.from_env()
