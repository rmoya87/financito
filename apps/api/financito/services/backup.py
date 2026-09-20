from __future__ import annotations
import hashlib,json,os,shutil,tarfile,tempfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from ..config import settings
MAGIC=b"FINANCITO-BACKUP-1\n";AAD=b"financito-backup-v1"

def _key(passphrase:str,salt:bytes)->bytes:return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(passphrase.encode())
def _safe_destination(raw:str)->Path:
    p=Path(raw).expanduser().resolve();p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists() and p.is_symlink():raise ValueError("Backup destination cannot be a symlink")
    return p
def create_backup(passphrase:str,destination:str)->dict:
    from ..db import engine
    dest=_safe_destination(destination)
    with engine.begin() as conn:conn.exec_driver_sql("PRAGMA wal_checkpoint(FULL)")
    with tempfile.TemporaryDirectory(dir=settings.data_dir) as tmp:
        root=Path(tmp);payload=root/"payload";payload.mkdir()
        shutil.copy2(settings.db_path,payload/"financito.db")
        if settings.vault_dir.exists():shutil.copytree(settings.vault_dir,payload/"vault",dirs_exist_ok=True)
        manifest={}
        for f in payload.rglob("*"):
            if f.is_file():manifest[str(f.relative_to(payload))]=hashlib.sha256(f.read_bytes()).hexdigest()
        (payload/"manifest.json").write_text(json.dumps({"version":1,"files":manifest},sort_keys=True))
        archive=root/"archive.tar.gz"
        with tarfile.open(archive,"w:gz") as tar:tar.add(payload,arcname="payload")
        plain=archive.read_bytes();salt=os.urandom(16);nonce=os.urandom(12);cipher=AESGCM(_key(passphrase,salt)).encrypt(nonce,plain,AAD)
        dest.write_bytes(MAGIC+salt+nonce+cipher)
    digest=hashlib.sha256(dest.read_bytes()).hexdigest()
    return {"path":str(dest),"sha256":digest,"size":dest.stat().st_size}

def stage_restore(passphrase:str,path:str)->dict:
    src=Path(path).expanduser().resolve(strict=True);data=src.read_bytes()
    if not data.startswith(MAGIC):raise ValueError("Unsupported backup format")
    off=len(MAGIC);salt=data[off:off+16];nonce=data[off+16:off+28];cipher=data[off+28:]
    plain=AESGCM(_key(passphrase,salt)).decrypt(nonce,cipher,AAD)
    staging=settings.data_dir/"restore-staging"
    if staging.exists():shutil.rmtree(staging)
    staging.mkdir()
    archive=staging/"archive.tar.gz";archive.write_bytes(plain)
    with tarfile.open(archive,"r:gz") as tar:
        for member in tar.getmembers():
            target=(staging/member.name).resolve()
            if staging.resolve() not in target.parents and target!=staging.resolve():raise ValueError("Unsafe backup path")
        tar.extractall(staging)
    payload=staging/"payload";manifest=json.loads((payload/"manifest.json").read_text())
    for rel,digest in manifest["files"].items():
        f=(payload/rel).resolve()
        if payload.resolve() not in f.parents:raise ValueError("Unsafe manifest path")
        if hashlib.sha256(f.read_bytes()).hexdigest()!=digest:raise ValueError(f"Checksum mismatch: {rel}")
    marker=settings.data_dir/".restore-pending";marker.write_text(str(payload))
    return {"verified":True,"restart_required":True,"file_count":len(manifest["files"])}

def apply_pending_restore()->bool:
    marker=settings.data_dir/".restore-pending"
    if not marker.exists():return False
    payload=Path(marker.read_text()).resolve();db=payload/"financito.db"
    if not db.exists():raise RuntimeError("Pending restore has no database")
    settings.db_path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(db,settings.db_path)
    v=payload/"vault"
    if v.exists():
        if settings.vault_dir.exists():shutil.rmtree(settings.vault_dir)
        shutil.copytree(v,settings.vault_dir)
    shutil.rmtree(settings.data_dir/"restore-staging",ignore_errors=True);marker.unlink(missing_ok=True);return True
