from __future__ import annotations
from contextlib import contextmanager
import os,secrets
from sqlalchemy import create_engine,event
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .config import settings

class Base(DeclarativeBase): pass

_db_key:str|None=None
if settings.allow_plaintext_sqlite:
    import sqlite3 as _dbapi
else:
    try:
        from sqlcipher3 import dbapi2 as _dbapi
        import keyring
    except ImportError as exc:
        raise RuntimeError("Stable runtime requires sqlcipher3 and keyring") from exc
    _db_key=os.getenv("FINANCITO_DB_KEY")
    if not _db_key:
        _db_key=keyring.get_password("Financito","database")
        if not _db_key:
            _db_key=secrets.token_hex(32)
            keyring.set_password("Financito","database",_db_key)

engine=create_engine(f"sqlite:///{settings.db_path}",module=_dbapi,connect_args={"check_same_thread":False},future=True)

@event.listens_for(engine,"connect")
def _configure(dbapi_connection,_):
    cursor=dbapi_connection.cursor()
    if _db_key:
        if any(c not in "0123456789abcdefABCDEF" for c in _db_key): raise RuntimeError("Invalid database key material")
        cursor.execute(f'PRAGMA key = "x\'{_db_key}\'"')
        version=cursor.execute("PRAGMA cipher_version").fetchone()
        if not version or not version[0]: raise RuntimeError("SQLCipher is not active")
    cursor.execute("PRAGMA foreign_keys=ON");cursor.execute("PRAGMA journal_mode=WAL");cursor.execute("PRAGMA synchronous=FULL")
    cursor.close()
    try:
        import sqlite_vec
        dbapi_connection.enable_load_extension(True);sqlite_vec.load(dbapi_connection);dbapi_connection.enable_load_extension(False)
    except Exception:
        try: dbapi_connection.enable_load_extension(False)
        except Exception: pass

SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)

@contextmanager
def session_scope():
    s=SessionLocal()
    try: yield s;s.commit()
    except Exception:s.rollback();raise
    finally:s.close()

def init_db()->None:
    from . import models,models_extended
    Base.metadata.create_all(bind=engine)
