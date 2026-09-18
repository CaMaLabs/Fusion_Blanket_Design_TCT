#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
AUDIT_PYTHON="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}/bin/python"
if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "ERROR: audit Python not found: $AUDIT_PYTHON"
  exit 96
fi
"$AUDIT_PYTHON" -u tools/tct_mechanism_explorer/native_precursor_horizon_reachability_audit.py
OUT="validation_runs/m3dc1_tct_native_precursor_horizon_reachability/native_precursor_horizon_reachability_summary.json"
echo "===== NATIVE TCT PRECURSOR HORIZON REACHABILITY ====="
jq '{classification,pipeline_failure,claim_boundary,parent_classification,zero_equivalence_status,frozen_gates,calibrated_timing,reachability,runtime_reference,decision}' "$OUT"
