#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
PY="$REPO/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
cd "$REPO/tools/tct_mechanism_explorer"
"$PY" audit_segmented_electrode_energy_matched_control.py
