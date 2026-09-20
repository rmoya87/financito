#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FINANCITO_ALLOW_PLAINTEXT_SQLITE=1
export FINANCITO_DATA_DIR="${FINANCITO_DATA_DIR:-$ROOT/.local-data}"
export FINANCITO_VAULT_DIR="${FINANCITO_VAULT_DIR:-$ROOT/.local-data/vault}"
mkdir -p "$FINANCITO_VAULT_DIR"
( cd "$ROOT/apps/api" && PYTHONPATH=. uvicorn financito.main:app --host 127.0.0.1 --port 8765 --reload ) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
cd "$ROOT/apps/web"
npm run dev
