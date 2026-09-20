from __future__ import annotations
import threading,time
from pathlib import Path
from ..config import settings
from ..db import SessionLocal
from .documents import index_document
SUPPORTED={".pdf",".png",".jpg",".jpeg",".heic",".tiff",".bmp",".docx",".xlsx",".xlsm",".csv",".txt",".json"}
class VaultWatcher:
    def __init__(self,interval:float=10):self.interval=interval;self.stop_event=threading.Event();self.thread=None;self.seen={}
    def scan_once(self):
        if not settings.vault_dir.exists():return
        for path in settings.vault_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED:continue
            try:stamp=(path.stat().st_mtime_ns,path.stat().st_size)
            except OSError:continue
            if self.seen.get(str(path))==stamp:continue
            with SessionLocal() as db:
                try:index_document(db,str(path),"unknown");db.commit();self.seen[str(path)]=stamp
                except Exception:db.rollback()
    def _run(self):
        while not self.stop_event.is_set():self.scan_once();self.stop_event.wait(self.interval)
    def start(self):
        self.scan_once();self.thread=threading.Thread(target=self._run,name="financito-vault",daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=2)
