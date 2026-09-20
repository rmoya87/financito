#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-update}"
ROOT="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
LOG_DIR="$HOME/.financito"
LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

title() { printf '\n============================================================\n  %s\n============================================================\n' "$1"; }
info() { printf '• %s\n' "$1"; }
ok() { printf '✓ %s\n' "$1"; }
die() {
  printf '\n✗ %s\n' "$1" >&2
  printf '\nRegistro: %s\n' "$LOG_FILE" >&2
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display dialog "Financito no ha podido arrancar. Revisa la ventana de Terminal o el archivo ~/.financito/launcher.log." with title "Financito" buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
  fi
  exit 1
}
trap 'die "Se produjo un error en la línea $LINENO."' ERR

cd "$ROOT"
[[ -d .git ]] || die "No encuentro el repositorio de Financito en: $ROOT"

title "Financito para macOS"
info "Carpeta: $ROOT"

if [[ "$MODE" == "update" ]]; then
  title "1/5 · Comprobando actualizaciones"

  # Guardamos cualquier cambio local antes de tocar Git. No se pierde nada.
  if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    stamp="$(date '+%Y-%m-%d_%H-%M-%S')"
    info "Hay cambios locales. Los guardo como copia de seguridad."
    git stash push -u -m "Financito auto-backup $stamp" >/dev/null
    ok "Copia guardada en git stash."
  fi

  if git fetch origin main; then
    current_branch="$(git branch --show-current || true)"
    if [[ "$current_branch" != "main" ]]; then
      git switch main
    fi
    git merge --ff-only origin/main
    ok "Código actualizado a origin/main."
  else
    info "No hay conexión con GitHub. Continuaré con la versión local instalada."
  fi
else
  title "1/5 · Inicio sin actualizar"
  info "Se usará la versión local actual."
fi

title "2/5 · Comprobando Python"
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
    then
      PYTHON="$(command -v "$candidate")"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  if command -v brew >/dev/null 2>&1; then
    info "Python 3.12+ no está instalado. Lo instalaré con Homebrew."
    brew install python@3.13
    PYTHON="$(command -v python3.13 || true)"
  fi
fi
[[ -n "$PYTHON" ]] || die "Necesito Python 3.12 o superior."

if [[ ! -x .venv/bin/python ]]; then
  info "Creo el entorno privado de Python."
  "$PYTHON" -m venv .venv
elif ! .venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
then
  stamp="$(date '+%Y-%m-%d_%H-%M-%S')"
  mv .venv ".venv-old-$stamp"
  "$PYTHON" -m venv .venv
fi
ok "Python: $(.venv/bin/python --version)"

title "3/5 · Preparando dependencias"
HEAD="$(git rev-parse HEAD)"
STATE_FILE=".venv/.financito-installed-head"
INSTALLED_HEAD="$(cat "$STATE_FILE" 2>/dev/null || true)"
NEEDS_BUILD=0

if [[ "$HEAD" != "$INSTALLED_HEAD" || ! -f apps/web/out/index.html ]]; then
  NEEDS_BUILD=1
fi

if [[ "$NEEDS_BUILD" == "1" ]]; then
  info "Instalo/actualizo el backend."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e 'apps/api[dev]'

  if ! command -v npm >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      info "Node/npm no está instalado. Lo instalaré con Homebrew."
      brew install node@24
      export PATH="/opt/homebrew/opt/node@24/bin:/usr/local/opt/node@24/bin:$PATH"
    fi
  fi
  command -v npm >/dev/null 2>&1 || die "Necesito Node.js/npm para construir la interfaz."

  if ! command -v tesseract >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      info "Instalo Tesseract para OCR."
      brew install tesseract
    else
      info "Tesseract no está instalado. La app funcionará, pero el OCR de imágenes no estará disponible."
    fi
  fi

  info "Instalo dependencias de la interfaz."
  (
    cd apps/web
    npm install --no-package-lock --no-audit --no-fund
    npm run build
  )
  printf '%s\n' "$HEAD" > "$STATE_FILE"
  ok "Aplicación preparada."
else
  ok "La versión actual ya estaba instalada; no recompilo."
fi

title "4/5 · Comprobación rápida"
.venv/bin/python -m compileall -q apps/api/financito
[[ -f apps/web/out/index.html ]] || die "No encuentro la interfaz compilada."
ok "Backend e interfaz preparados."

title "5/5 · Arrancando"
info "Financito se abrirá en tu navegador."
info "Para cerrarlo, vuelve a esta ventana y pulsa Control+C."
info "Log: $LOG_FILE"
export FINANCITO_FRONTEND_DIR="$ROOT/apps/web/out"
export PYTHONPATH="$ROOT/apps/api${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT/apps/api"
exec "$ROOT/.venv/bin/python" -m financito.launcher
