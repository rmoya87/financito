from __future__ import annotations

import json,os,tempfile
from pathlib import Path
from . import __init__ as _unused
from ..config import settings

PREFERENCES_PATH=settings.data_dir/"preferences.json"
ALLOWED={"local_ai_model","embedding_model","enable_banking_redirect_url"}

def read_preferences()->dict:
    if not PREFERENCES_PATH.exists():
        return {}
    try:
        data=json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        return {k:str(v) for k,v in data.items() if k in ALLOWED and isinstance(v,str)}
    except Exception:
        return {}

def update_preferences(values:dict)->dict:
    current=read_preferences()
    for key,value in values.items():
        if key not in ALLOWED:
            continue
        if value is None or str(value).strip()=="":
            current.pop(key,None)
        else:
            current[key]=str(value).strip()
    PREFERENCES_PATH.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".preferences-",suffix=".json",dir=PREFERENCES_PATH.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(current,handle,ensure_ascii=False,sort_keys=True,indent=2)
            handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,PREFERENCES_PATH)
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass
    return current

def effective_ai_models()->tuple[str,str]:
    p=read_preferences()
    return p.get("local_ai_model",settings.local_ai_model),p.get("embedding_model",settings.embedding_model)


def effective_banking_redirect_url()->str:
    p=read_preferences()
    return p.get("enable_banking_redirect_url",os.getenv("FINANCITO_ENABLE_BANKING_REDIRECT_URL","")).strip()
