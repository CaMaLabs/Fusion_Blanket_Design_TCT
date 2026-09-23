#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
AUDIT_PYTHON="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}/bin/python"
if [[ ! -x "$AUDIT_PYTHON" ]]; then echo "ERROR: audit Python missing: $AUDIT_PYTHON"; exit 96; fi
"$AUDIT_PYTHON" tools/tct_mechanism_explorer/audit_native_time_normalization_physical_conversion.py
