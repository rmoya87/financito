from __future__ import annotations

import hmac
import secrets
import time
from hashlib import sha256
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .services.runtime_metrics import record as record_runtime_metric


ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", f"localhost:{settings.port}", f"127.0.0.1:{settings.port}"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def sign_session(session_id: str) -> str:
    signature = hmac.new(settings.session_secret.encode(), session_id.encode(), sha256).hexdigest()
    return f"{session_id}.{signature}"


def verify_session(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    session_id, signature = value.rsplit(".", 1)
    expected = hmac.new(settings.session_secret.encode(), session_id.encode(), sha256).hexdigest()
    return session_id if hmac.compare_digest(signature, expected) else None


def csrf_for(session_id: str) -> str:
    return hmac.new(settings.session_secret.encode(), f"csrf:{session_id}".encode(), sha256).hexdigest()


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        host = request.headers.get("host", "").lower()
        if host not in ALLOWED_HOSTS and not host.startswith("testserver"):
            return Response("Invalid host", status_code=400)
        origin = request.headers.get("origin")
        if origin and not any(origin.startswith(prefix) for prefix in ("http://localhost", "http://127.0.0.1", "https://localhost", "https://127.0.0.1")):
            return Response("Invalid origin", status_code=403)
        if request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/session":
            session_id = verify_session(request.cookies.get("financito_session"))
            if not session_id:
                return Response("Local session required", status_code=401)
            if request.method not in SAFE_METHODS:
                csrf = request.headers.get("x-csrf-token")
                if not csrf or not hmac.compare_digest(csrf, csrf_for(session_id)):
                    return Response("CSRF validation failed", status_code=403)
        started=time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            if request.url.path.startswith("/api/"):
                record_runtime_metric(request.method,request.url.path,500,(time.perf_counter()-started)*1000)
            raise
        if request.url.path.startswith("/api/"):
            record_runtime_metric(request.method,request.url.path,response.status_code,(time.perf_counter()-started)*1000)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def create_session(response: Response, existing_cookie: str | None = None) -> dict:
    # Reuse a valid browser session instead of rotating the cookie on every
    # GET /session. Rotating it invalidated CSRF tokens cached by other pages
    # or tabs and produced intermittent 403 responses on otherwise valid POSTs.
    session_id = verify_session(existing_cookie)
    if session_id is None:
        session_id = secrets.token_urlsafe(24)
        response.set_cookie(
            "financito_session", sign_session(session_id), httponly=True, samesite="strict", secure=False,
            max_age=3600, path="/",
        )
    return {"csrf_token": csrf_for(session_id), "expires_in": 3600}
