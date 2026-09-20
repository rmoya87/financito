#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FINANCITO_FRONTEND_DIR="${FINANCITO_FRONTEND_DIR:-$ROOT/apps/web/out}"
export PYTHONPATH="$ROOT/apps/api${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT/apps/api"
exec python3 -m financito.launcher
