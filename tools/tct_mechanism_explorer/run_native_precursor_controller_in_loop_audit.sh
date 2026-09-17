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

# Reuse the existing fusion/BOUT++ analysis environment created for this repo.
# It already carries the Python-side analysis stack (numpy/netCDF4) and avoids
# Ubuntu's PEP-668-managed system Python. Do not create another venv here.
AUDIT_VENV="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}"
AUDIT_PYTHON="$AUDIT_VENV/bin/python"

if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "ERROR: existing audit venv Python not found: $AUDIT_PYTHON"
  exit 96
fi

echo "Using existing audit venv: $AUDIT_VENV"

# The live-baseline calibration audit reads normalization directly from C1.h5.
# Install h5py into the existing project venv only when it is absent.
if ! "$AUDIT_PYTHON" -c 'import h5py' >/dev/null 2>&1; then
  echo "h5py missing from existing audit venv; installing into $AUDIT_VENV ..."
  if ! "$AUDIT_PYTHON" -m pip install h5py; then
    echo "ERROR: h5py installation failed inside existing audit venv."
    exit 96
  fi
fi

# Dependency failure is infrastructure failure, never a calibration/physics
# classification. Verify the exact interpreter that will execute the audit.
if ! "$AUDIT_PYTHON" -c 'import h5py, sys; print("audit_python", sys.executable); print("h5py", h5py.__version__)'; then
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
