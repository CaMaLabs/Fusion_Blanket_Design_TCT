#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
AUDIT_VENV="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}"
AUDIT_PYTHON="$AUDIT_VENV/bin/python"
if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "ERROR: existing audit venv Python not found: $AUDIT_PYTHON"
  exit 96
fi
echo "audit_python $AUDIT_PYTHON"
"$AUDIT_PYTHON" tools/tct_mechanism_explorer/audit_native_magnetic_probe_time_normalization_provenance.py
