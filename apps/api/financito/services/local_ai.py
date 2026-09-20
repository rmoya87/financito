from __future__ import annotations
import json
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from ..config import settings
from .preferences import effective_ai_models

def _validate(url:str)->None:
    p=urlparse(url)
    if p.scheme not in {"http","https"} or p.hostname not in {"127.0.0.1","localhost","::1"}:
        raise ValueError("Local AI endpoint must be loopback-only")

def _json(path:str,body:dict|None=None,timeout:float=15)->dict:
    _validate(settings.local_ai_url);url=f"{settings.local_ai_url.rstrip('/')}{path}"
    req=Request(url,data=None if body is None else json.dumps(body).encode(),headers={"Content-Type":"application/json"},method="GET" if body is None else "POST")
    with urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def status()->dict:
    chat_model,embedding_model=effective_ai_models()
    try:
        data=_json("/api/tags",timeout=1)
        names=[m.get("name") for m in data.get("models",[]) if m.get("name")]
        return {"available":True,"configured_model":chat_model or None,"embedding_model":embedding_model or None,"models":names}
    except Exception:
        return {"available":False,"configured_model":chat_model or None,"embedding_model":embedding_model or None,"models":[]}

def embed(inputs:str|list[str])->list[list[float]]:
    _,embedding_model=effective_ai_models()
    if not embedding_model:raise RuntimeError("No local embedding model configured")
    data=_json("/api/embed",{"model":embedding_model,"input":inputs},timeout=60)
    return data["embeddings"]

def ask(prompt:str,context:str)->str:
    chat_model,_=effective_ai_models()
    if not chat_model:raise RuntimeError("No local AI model configured")
    data=_json("/api/generate",{"model":chat_model,"stream":False,"prompt":"Eres Financito. Responde en español. No inventes cifras, normativa ni fuentes. Las cifras financieras solo pueden proceder del contexto calculado por herramientas. Si falta evidencia, indícalo.\n\nCONTEXTO VERIFICADO:\n"+context+"\n\nPREGUNTA:\n"+prompt},timeout=90)
    return data.get("response","")
