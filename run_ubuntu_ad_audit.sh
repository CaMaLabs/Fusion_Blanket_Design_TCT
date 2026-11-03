#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_DIR="${RUN_DIR:-validation_runs/ubuntu_ad_audit_default}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 127
fi

# Ensure repository modules are importable from subprocesses invoked through
# scripts/*.py. Preserve any caller-supplied PYTHONPATH after the repo root.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

ARGS=(--run-dir "$RUN_DIR")

if "$PYTHON_BIN" -c 'import pytest' >/dev/null 2>&1; then
  ARGS+=(--with-pytest)
else
  echo "[info] pytest is not installed in $PYTHON_BIN; skipping optional pytest stage."
fi

if command -v openmc >/dev/null 2>&1; then
  ARGS+=(--with-openmc)
else
  echo "[info] openmc executable not found; running A + D inventory without OpenMC transport."
fi

exec "$PYTHON_BIN" scripts/run_ubuntu_ad_audit.py "${ARGS[@]}" "$@"
