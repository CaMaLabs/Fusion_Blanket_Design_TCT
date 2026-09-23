#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
PY="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
"$PY" -m unittest tools/tct_mechanism_explorer/tests/test_segmented_electrodes.py -v
"$PY" tools/tct_mechanism_explorer/run_segmented_electrode_audit.py
