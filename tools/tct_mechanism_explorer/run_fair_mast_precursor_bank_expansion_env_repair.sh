#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Required analysis interpreter not found: $PY" >&2
  exit 2
fi
if ! "$PY" - <<'PY' >/dev/null 2>&1
import numpy, scipy, zarr
PY
then
  echo "Required analysis dependencies missing from $PY (numpy, scipy, zarr); refusing to install or alter dependencies." >&2
  exit 2
fi
exec "$PY" tools/tct_mechanism_explorer/run_fair_mast_precursor_bank_expansion.py
