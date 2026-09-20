#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -t financito-runner.XXXXXX)"
cleanup(){ rm -f "$TMP"; }
trap cleanup EXIT
cp "$ROOT/scripts/mac-runner.sh" "$TMP"
chmod +x "$TMP"
bash "$TMP" no-update "$ROOT"
status=$?
if [[ $status -ne 0 ]]; then
  printf '\nPulsa Intro para cerrar esta ventana...'
  read -r _
fi
exit $status
