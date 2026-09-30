#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
CANDIDATES=(
  "$ROOT/.venv-dudson/bin/python"
  "$ROOT/.venv/bin/python"
  "/home/ubuntu/work/openmc/sweep/.venv-dudson/bin/python"
)
for py in "${CANDIDATES[@]}"; do
  if [[ -x "$py" ]] && "$py" - <<'PY' >/dev/null 2>&1
import numpy, scipy, zarr
PY
  then
    exec "$py" tools/tct_mechanism_explorer/run_fair_mast_precursor_bank_expansion.py
  fi
done
echo "No existing Python environment with numpy, scipy, and zarr was found; refusing to install or alter dependencies." >&2
exit 2
