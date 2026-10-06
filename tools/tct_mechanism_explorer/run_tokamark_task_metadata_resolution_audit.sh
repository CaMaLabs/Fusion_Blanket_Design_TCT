#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Required interpreter missing: $PY" >&2
  exit 2
fi
exec "$PY" tools/tct_mechanism_explorer/run_tokamark_task_metadata_resolution_audit.py
