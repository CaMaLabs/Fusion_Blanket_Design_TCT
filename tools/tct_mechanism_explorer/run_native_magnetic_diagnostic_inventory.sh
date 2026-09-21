#!/usr/bin/env bash
set -uo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
AUDIT_VENV="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}"
PY="$AUDIT_VENV/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: existing audit venv Python not found: $PY"
  exit 96
fi
if ! "$PY" -c 'import h5py' >/dev/null 2>&1; then
  echo "h5py missing from existing audit venv; installing into $AUDIT_VENV ..."
  "$PY" -m pip install h5py || exit 96
fi
"$PY" -u tools/tct_mechanism_explorer/native_magnetic_diagnostic_inventory.py
