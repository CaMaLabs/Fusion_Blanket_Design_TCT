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
if ! "$AUDIT_PYTHON" -c 'import h5py' >/dev/null 2>&1; then
  echo "ERROR: h5py unavailable in established audit venv: $AUDIT_VENV"
  exit 96
fi
"$AUDIT_PYTHON" -c 'import h5py,sys; print("audit_python",sys.executable); print("h5py",h5py.__version__)'
"$AUDIT_PYTHON" tools/tct_mechanism_explorer/audit_native_magnetic_probe_run_hdf5_schema.py
