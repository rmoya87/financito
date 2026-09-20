from __future__ import annotations

import socket
import threading
import time
import webbrowser

import uvicorn

from .config import settings


def _wait_and_open() -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", settings.port), timeout=0.25):
                webbrowser.open(f"http://127.0.0.1:{settings.port}")
                return
        except OSError:
            time.sleep(0.15)


def main() -> None:
    if settings.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing to start outside loopback")
    threading.Thread(target=_wait_and_open, daemon=True).start()
    uvicorn.run("financito.main:app", host="127.0.0.1", port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
