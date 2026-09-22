#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
try:
    import h5py
except Exception as exc:
    raise SystemExit(f"h5py unavailable in m3dc1-deps environment: {exc}")
PY
python3 tools/tct_mechanism_explorer/audit_native_magnetic_probe_observable.py
