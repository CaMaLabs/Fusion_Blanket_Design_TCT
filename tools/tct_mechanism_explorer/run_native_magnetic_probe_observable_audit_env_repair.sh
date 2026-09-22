#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps

# Use the established project audit venv rather than whichever python3 Spack
# happens to put first on PATH. This is the same venv used by the native
# precursor/HDF5 audit path.
AUDIT_VENV="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}"
AUDIT_PYTHON="$AUDIT_VENV/bin/python"

if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "ERROR: existing audit venv Python not found: $AUDIT_PYTHON"
  exit 96
fi

echo "Using existing audit venv: $AUDIT_VENV"
"$AUDIT_PYTHON" -c 'import sys; print("audit_python", sys.executable)'

# h5py is an analysis dependency, not solver physics. Bootstrap it only into
# the exact established audit venv, and only when absent.
if ! "$AUDIT_PYTHON" -c 'import h5py' >/dev/null 2>&1; then
  echo "h5py missing from existing audit venv; installing into $AUDIT_VENV ..."
  "$AUDIT_PYTHON" -m pip install h5py
fi

"$AUDIT_PYTHON" -c 'import h5py, sys; print("verified_python", sys.executable); print("h5py", h5py.__version__)'
"$AUDIT_PYTHON" tools/tct_mechanism_explorer/audit_native_magnetic_probe_observable.py
