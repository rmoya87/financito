from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..config import settings


def _validate_local_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Local AI endpoint must be loopback-only")


def status() -> dict:
    _validate_local_url(settings.local_ai_url)
    try:
        with urlopen(f"{settings.local_ai_url.rstrip('/')}/api/tags", timeout=1.0) as response:
            data = json.loads(response.read().decode())
        return {"available": True, "configured_model": settings.local_ai_model or None, "models": [m.get("name") for m in data.get("models", [])]}
    except Exception:
        return {"available": False, "configured_model": settings.local_ai_model or None, "models": []}


def ask(prompt: str, context: str) -> str:
    _validate_local_url(settings.local_ai_url)
    if not settings.local_ai_model:
        raise RuntimeError("No local AI model configured")
    body = json.dumps({"model":settings.local_ai_model,"stream":False,"prompt":"Eres Financito. Responde en español. No inventes cifras ni fuentes. Usa exclusivamente el contexto verificado proporcionado. Si falta información, dilo.\n\n"+f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{prompt}"}).encode()
    req = Request(f"{settings.local_ai_url.rstrip('/')}/api/generate", data=body, headers={"Content-Type":"application/json"}, method="POST")
    with urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode())
    return data.get("response", "")
