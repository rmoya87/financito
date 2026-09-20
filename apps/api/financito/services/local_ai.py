from __future__ import annotations
import json
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from urllib.request import Request,urlopen

from ..config import settings
from .preferences import effective_ai_models

def _validate(url:str)->None:
    p=urlparse(url)
    if p.scheme not in {"http","https"} or p.hostname not in {"127.0.0.1","localhost","::1"}:
        raise ValueError("Local AI endpoint must be loopback-only")

def _json(path:str,body:dict|None=None,timeout:float=15)->dict:
    _validate(settings.local_ai_url)
    url=f"{settings.local_ai_url.rstrip('/')}{path}"
    req=Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type":"application/json"},
        method="GET" if body is None else "POST",
    )
    with urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def _model_names(data:dict)->list[str]:
    names=[]
    for item in data.get("models",[]) or []:
        for key in ("name","model"):
            value=item.get(key)
            if value and str(value) not in names:names.append(str(value))
    return names

def _is_model_ready(configured:str,names:list[str])->bool:
    if not configured:return False
    if configured in names:return True
    # Ollama may expose an implicit :latest tag in one place and omit it in another.
    if ":" not in configured and configured+":latest" in names:return True
    if configured.endswith(":latest") and configured[:-7] in names:return True
    return False

def status()->dict:
    chat_model,embedding_model=effective_ai_models()
    try:
        data=_json("/api/tags",timeout=2.5)
        names=_model_names(data)
        return {
            "available":True,
            "endpoint":settings.local_ai_url,
            "configured_model":chat_model or None,
            "embedding_model":embedding_model or None,
            "models":names,
            "chat_ready":_is_model_ready(chat_model,names),
            "embedding_ready":_is_model_ready(embedding_model,names),
            "error":None,
        }
    except Exception as exc:
        return {
            "available":False,
            "endpoint":settings.local_ai_url,
            "configured_model":chat_model or None,
            "embedding_model":embedding_model or None,
            "models":[],
            "chat_ready":False,
            "embedding_ready":False,
            "error":f"{type(exc).__name__}: {exc}",
        }

def embed(inputs:str|list[str])->list[list[float]]:
    _,embedding_model=effective_ai_models()
    if not embedding_model:raise RuntimeError("No local embedding model configured")
    data=_json("/api/embed",{"model":embedding_model,"input":inputs,"keep_alive":"10m"},timeout=120)
    return data["embeddings"]

def _generate(prompt:str,*,json_mode:bool=False,timeout:float=180)->str:
    chat_model,_=effective_ai_models()
    if not chat_model:raise RuntimeError("No local AI model configured")
    payload={
        "model":chat_model,
        "stream":False,
        "think":False,
        "keep_alive":"10m",
        "options":{"temperature":0},
        "prompt":prompt,
    }
    if json_mode:payload["format"]="json"
    try:
        data=_json("/api/generate",payload,timeout=timeout)
    except HTTPError as exc:
        # Older Ollama versions/models may reject the think option. Retry without it.
        if exc.code not in {400,404,422}:raise
        payload.pop("think",None)
        data=_json("/api/generate",payload,timeout=timeout)
    raw=str(data.get("response","")).strip()
    if not raw:
        thinking=str(data.get("thinking","")).strip()
        if thinking:
            raise RuntimeError("El modelo devolvió razonamiento interno pero ninguna respuesta final. Actualiza Ollama o usa un modelo compatible con think=false.")
        raise RuntimeError("Ollama respondió sin contenido en el campo response")
    return raw

def generate_json(prompt:str,timeout:float=180)->dict:
    raw=_generate(prompt,json_mode=True,timeout=timeout)
    try:return json.loads(raw)
    except json.JSONDecodeError:
        start=raw.find("{");end=raw.rfind("}")
        if start>=0 and end>start:return json.loads(raw[start:end+1])
        raise RuntimeError("Local AI did not return valid JSON")

def ask(prompt:str,context:str)->str:
    return _generate(
        "Eres Financito. Responde en español. No inventes cifras, normativa ni fuentes. "
        "Las cifras financieras solo pueden proceder del contexto calculado por herramientas. "
        "Distingue siempre evidencia confirmada de evidencia documental inferida o dudosa: un fact solo es confirmado "
        "si status=confirmed y user_verified=true. No uses hechos inferred/ambiguous como base cierta de cálculos o "
        "conclusiones materiales. Si falta evidencia, indícalo.\n\n"
        "CONTEXTO LOCAL ESTRUCTURADO Y DOCUMENTAL:\n"+context+"\n\nPREGUNTA:\n"+prompt,
        timeout=180,
    )

def diagnose()->dict:
    info=status()
    if not info["available"]:
        return {**info,"generation_ok":False,"latency_ms":None,"sample":None}
    if not info["configured_model"]:
        return {**info,"generation_ok":False,"latency_ms":None,"sample":None,"error":"No hay modelo de chat configurado"}
    if not info["chat_ready"]:
        return {**info,"generation_ok":False,"latency_ms":None,"sample":None,"error":f"El modelo configurado no aparece en Ollama: {info['configured_model']}"}
    started=time.monotonic()
    try:
        response=_generate("Responde únicamente con la palabra OK.",timeout=180)
        return {**info,"generation_ok":bool(response),"latency_ms":int((time.monotonic()-started)*1000),"sample":response[:120],"error":None}
    except Exception as exc:
        return {**info,"generation_ok":False,"latency_ms":int((time.monotonic()-started)*1000),"sample":None,"error":f"{type(exc).__name__}: {exc}"}
