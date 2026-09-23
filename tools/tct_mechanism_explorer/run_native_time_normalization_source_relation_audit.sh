#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
AUDIT_PYTHON="${TCT_AUDIT_VENV:-/home/ubuntu/work/openmc/sweep/.venv-dudson}/bin/python"
if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "ERROR: audit venv Python not found: $AUDIT_PYTHON"
  exit 96
fi
echo "audit_python $AUDIT_PYTHON"
"$AUDIT_PYTHON" -u tools/tct_mechanism_explorer/audit_native_time_normalization_source_relation.py
