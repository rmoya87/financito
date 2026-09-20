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
        return {"available":True,"configured_model":chat_model or None,"embedding_model":embedding_model or None,"models":names,"chat_ready":bool(chat_model and chat_model in names),"embedding_ready":bool(embedding_model and embedding_model in names)}
    except Exception:
        return {"available":False,"configured_model":chat_model or None,"embedding_model":embedding_model or None,"models":[],"chat_ready":False,"embedding_ready":False}

def embed(inputs:str|list[str])->list[list[float]]:
    _,embedding_model=effective_ai_models()
    if not embedding_model:raise RuntimeError("No local embedding model configured")
    data=_json("/api/embed",{"model":embedding_model,"input":inputs},timeout=90)
    return data["embeddings"]

def generate_json(prompt:str,timeout:float=180)->dict:
    chat_model,_=effective_ai_models()
    if not chat_model:raise RuntimeError("No local AI model configured")
    payload={"model":chat_model,"stream":False,"format":"json","think":False,"options":{"temperature":0},"prompt":prompt}
    try:data=_json("/api/generate",payload,timeout=timeout)
    except Exception:
        payload.pop("think",None);data=_json("/api/generate",payload,timeout=timeout)
    raw=str(data.get("response","")).strip()
    try:return json.loads(raw)
    except json.JSONDecodeError:
        start=raw.find("{");end=raw.rfind("}")
        if start>=0 and end>start:return json.loads(raw[start:end+1])
        raise RuntimeError("Local AI did not return valid JSON")

def ask(prompt:str,context:str)->str:
    chat_model,_=effective_ai_models()
    if not chat_model:raise RuntimeError("No local AI model configured")
    data=_json("/api/generate",{"model":chat_model,"stream":False,"prompt":"Eres Financito. Responde en español. No inventes cifras, normativa ni fuentes. Las cifras financieras solo pueden proceder del contexto calculado por herramientas. Distingue siempre evidencia confirmada de evidencia documental inferida o dudosa: un fact solo es confirmado si status=confirmed y user_verified=true. No uses hechos inferred/ambiguous como base cierta de cálculos o conclusiones materiales. Si falta evidencia, indícalo.\n\nCONTEXTO LOCAL ESTRUCTURADO Y DOCUMENTAL:\n"+context+"\n\nPREGUNTA:\n"+prompt},timeout=90)
    return data.get("response","")
