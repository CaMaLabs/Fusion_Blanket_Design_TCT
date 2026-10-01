#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Required analysis interpreter not found: $PY" >&2
  exit 2
fi
exec "$PY" tools/tct_mechanism_explorer/run_tcabr_precursor_cache_audit.py
