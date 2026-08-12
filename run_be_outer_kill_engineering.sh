#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 127
fi

if [[ " $* " != *" --plan-only "* ]] && ! command -v openmc >/dev/null 2>&1; then
  echo "OpenMC executable not found on PATH. Activate the OpenMC environment or use --plan-only." >&2
  exit 127
fi

exec "$PYTHON_BIN" scripts/run_be_outer_kill_engineering_openmc.py "$@"
