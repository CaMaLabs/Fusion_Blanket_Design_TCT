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
# Keep that scientific check authoritative, but make the worker self-provision
# the lightweight Python reader if the active M3D-C1 environment lacks it.
if ! python3 -c 'import h5py' >/dev/null 2>&1; then
  echo "h5py missing from active m3dc1-deps Python; bootstrapping dependency..."
  if ! python3 -m pip --version >/dev/null 2>&1; then
    python3 -m ensurepip --user >/dev/null 2>&1 || true
  fi
  python3 -m pip install --user h5py || python3 -m pip install h5py || true
fi

# Dependency failure is an infrastructure failure, not a calibration or physics
# result. Stop explicitly rather than letting the audit misclassify it.
if ! python3 -c 'import h5py; print("h5py", h5py.__version__)'; then
  echo "ERROR: h5py is still unavailable after bootstrap attempt."
  exit 96
fi

python3 -u tools/tct_mechanism_explorer/native_precursor_controller_in_loop_audit.py
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
