from __future__ import annotations

from hashlib import sha256
import threading
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Document
from .documents import SUPPORTED_SUFFIXES,index_document
from .document_ai import analyze_document,latest_analysis


class VaultWatcher:
    def __init__(self,interval:float=10):
        self.interval=interval
        self.stop_event=threading.Event()
        self.thread=None
        self.seen={}

    def scan_once(self):
        if not settings.vault_dir.exists():
            return
        for path in settings.vault_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            try:
                stamp=(path.stat().st_mtime_ns,path.stat().st_size)
            except OSError:
                continue
            key=str(path.resolve())
            if self.seen.get(key)==stamp:
                continue
            with SessionLocal() as db:
                try:
                    existing=db.scalar(select(Document).where(Document.file_path==key))
                    if existing is not None and existing.sha256==sha256(path.read_bytes()).hexdigest():
                        if latest_analysis(db,existing.id) is None:
                            try:analyze_document(db,existing)
                            except Exception:pass
                        db.commit()
                        self.seen[key]=stamp
                        continue

                    indexed=index_document(db,key,"unknown")
                    try:analyze_document(db,indexed.document)
                    except Exception:pass
                    db.commit()
                    self.seen[key]=stamp
                except Exception:
                    db.rollback()

    def _run(self):
        while not self.stop_event.is_set():
            self.scan_once()
            self.stop_event.wait(self.interval)

    def start(self):
        self.thread=threading.Thread(target=self._run,name="financito-vault",daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
