#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="$HOME/Library/Application Support/Financito"
VENV="$STATE_ROOT/runtime/.venv"
LOG_DIR="$HOME/Library/Logs/Financito"
LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$STATE_ROOT/runtime" "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

die(){
  printf 'Financito: %s\n' "$1" >&2
  /usr/bin/osascript -e 'display dialog "Financito no ha podido arrancar. Revisa ~/Library/Logs/Financito/launcher.log." with title "Financito" buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
  exit 1
}

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3,12) else 1)
PY
  then PYTHON="$(command -v "$candidate")";break;fi
done
if [[ -z "$PYTHON" ]] && command -v brew >/dev/null 2>&1; then
  brew install python@3.13
  PYTHON="$(command -v python3.13 || true)"
fi
[[ -n "$PYTHON" ]] || die "Se necesita Python 3.12 o superior."

if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi

APP_HASH="$(
  { find "$ROOT/apps/api/financito" -type f -name '*.py' -print; printf '%s\n' "$ROOT/apps/api/pyproject.toml"; } |
  LC_ALL=C sort |
  while IFS= read -r file; do shasum -a 256 "$file"; done |
  shasum -a 256 | awk '{print $1}'
)"
MARKER="$VENV/.financito-app-hash"
if [[ "$(cat "$MARKER" 2>/dev/null || true)" != "$APP_HASH" ]]; then
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install "$ROOT/apps/api"
  printf '%s\n' "$APP_HASH" > "$MARKER"
fi

export FINANCITO_FRONTEND_DIR="$ROOT/apps/web/out"
export PYTHONPATH="$ROOT/apps/api"
cd "$ROOT/apps/api"
exec "$VENV/bin/python" -m financito.launcher
