#!/usr/bin/env bash
set -uo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
SWEEP_TMP="${TCT_MPI_TMPDIR:-/tmp/tct-$USER}"
mkdir -p "$SWEEP_TMP"
export TMPDIR="$SWEEP_TMP"
export OMPI_MCA_orte_tmpdir_base="$SWEEP_TMP"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps

# The live-baseline calibration audit reads normalization directly from C1.h5.
# Prefer the active M3D-C1 Python when it already has h5py. If not, provision an
# isolated venv under the worker temp directory. This avoids PEP 668 writes to
# Ubuntu's externally-managed Python while keeping the physics environment clean.
AUDIT_PYTHON="python3"
if ! python3 -c 'import h5py' >/dev/null 2>&1; then
  H5PY_VENV="${TCT_H5PY_VENV:-$SWEEP_TMP/h5py-venv}"
  echo "h5py missing from active m3dc1-deps Python; provisioning isolated venv at $H5PY_VENV ..."

  if [[ ! -x "$H5PY_VENV/bin/python" ]]; then
    rm -rf "$H5PY_VENV"
    if ! python3 -m venv --system-site-packages "$H5PY_VENV"; then
      echo "ERROR: unable to create isolated h5py venv."
      exit 96
    fi
  fi

  if ! "$H5PY_VENV/bin/python" -c 'import h5py' >/dev/null 2>&1; then
    "$H5PY_VENV/bin/python" -m pip install --upgrade pip setuptools wheel || true
    if ! "$H5PY_VENV/bin/python" -m pip install h5py; then
      echo "ERROR: h5py installation failed inside isolated venv."
      exit 96
    fi
  fi

  AUDIT_PYTHON="$H5PY_VENV/bin/python"
fi

# Dependency failure is infrastructure failure, never a calibration/physics
# classification. Verify the exact interpreter that will execute the audit.
if ! "$AUDIT_PYTHON" -c 'import h5py; print("audit_python", __import__("sys").executable); print("h5py", h5py.__version__)'; then
  echo "ERROR: h5py remains unavailable to the audit interpreter."
  exit 96
fi

"$AUDIT_PYTHON" -u tools/tct_mechanism_explorer/native_precursor_controller_in_loop_audit.py
RC=$?
OUT="validation_runs/m3dc1_tct_native_precursor_controller_in_loop"
SUMMARY="$OUT/precursor_controller_in_loop_summary.json"
if [[ -f "$SUMMARY" ]]; then
  echo "===== NATIVE TCT PRECURSOR CONTROLLER-IN-LOOP ====="
  jq '{classification,pipeline_failure,claim_boundary,frozen_gates,precursor_authority,
       reason,physical_time_calibration,precursor_lead_ms,supervisor_decision,
       derived_native_times,zero_equivalence,arms,pacman_adaptation}' "$SUMMARY"
else
  echo "No summary produced."
fi
exit "$RC"
