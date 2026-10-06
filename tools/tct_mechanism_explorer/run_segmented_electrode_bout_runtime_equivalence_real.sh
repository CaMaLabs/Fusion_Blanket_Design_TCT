#!/usr/bin/env bash
set -euo pipefail
ROOT="${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
cd "$ROOT"
PY="${TCT_PYTHON:-$ROOT/.venv-dudson/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "Required TCT analysis interpreter not found: $PY" >&2
  exit 96
fi
exec "$PY" tools/tct_mechanism_explorer/run_segmented_electrode_bout_runtime_equivalence_real.py
