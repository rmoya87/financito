#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FINANCITO_ALLOW_PLAINTEXT_SQLITE=1
export FINANCITO_DATA_DIR="${FINANCITO_DATA_DIR:-/tmp/financito-validation}"
export FINANCITO_VAULT_DIR="${FINANCITO_VAULT_DIR:-/tmp/financito-validation/vault}"
mkdir -p "$FINANCITO_VAULT_DIR"
cd "$ROOT/apps/api"
PYTHONPATH=. python3 -m compileall -q financito
PYTHONPATH=. pytest
cd "$ROOT/apps/web"
npm run typecheck
npm run build
