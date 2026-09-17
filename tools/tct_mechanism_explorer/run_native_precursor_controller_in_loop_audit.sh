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
