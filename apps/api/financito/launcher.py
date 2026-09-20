from __future__ import annotations
import socket,threading,time,webbrowser
import uvicorn
from .config import settings
from .services.backup import apply_pending_restore

def _wait_and_open():
    deadline=time.time()+20
    while time.time()<deadline:
        try:
            with socket.create_connection(("127.0.0.1",settings.port),timeout=.25):
                webbrowser.open(f"http://127.0.0.1:{settings.port}");return
        except OSError:time.sleep(.15)

def main():
    if settings.host not in {"127.0.0.1","localhost","::1"}:raise SystemExit("Refusing to start outside loopback")
    apply_pending_restore()
    threading.Thread(target=_wait_and_open,daemon=True).start()
    uvicorn.run("financito.main:app",host="127.0.0.1",port=settings.port,log_level="info")
if __name__=="__main__":main()
