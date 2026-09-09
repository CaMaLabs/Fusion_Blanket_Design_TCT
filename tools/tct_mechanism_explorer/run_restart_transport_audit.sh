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

python3 tools/tct_mechanism_explorer/restart_transport_audit.py
RC=$?

OUT="validation_runs/m3dc1_restart_transport_audit"
SUMMARY="$OUT/restart_transport_summary.json"

echo
if [[ -f "$SUMMARY" ]]; then
  echo "===== RESTART TRANSPORT RESULT ====="
  jq '{
    classification,
    restart_chain_execution_pass,
    equal_time_metric_equivalence_pass,
    final_state_hash_comparison,
    segments: [.segments[] | {
      index,
      start,
      stop,
      restart,
      pass,
      error,
      execution_return_code: .execution.return_code,
      seed_matches_previous_final,
      state_hash_advanced,
      time_advanced_to_stop,
      last_extracted_time
    }],
    equivalence_checks: [.equivalence_checks[] | {
      time,
      pass,
      max_abs_metric_delta,
      max_scaled_error
    }]
  }' "$SUMMARY"

  echo
  echo "===== FAILED METRICS ====="
  jq '[
    .equivalence_checks[]
    | .time as $t
    | .by_metric // {}
    | to_entries[]
    | select(.value.pass == false)
    | {
        time: $t,
        metric: .key,
        baseline: .value.baseline,
        segmented: .value.segmented,
        delta: .value.delta,
        tolerance: .value.tolerance,
        scaled_error: .value.scaled_error
      }
  ]' "$SUMMARY"

  echo
  echo "===== FAILED SEGMENT LOG TAIL ====="
  jq -r '
    .segments[]
    | select(.pass == false)
    | "segment=\(.index) \(.start)->\(.stop) rc=\(.execution.return_code)\nerror=\(.error // \"\")\nC1stdout:\n\(.execution.C1stdout_tail // \"\")\nlauncher.stderr:\n\(.execution.launcher_stderr_tail // \"\")"
  ' "$SUMMARY"
else
  echo "restart audit did not produce $SUMMARY"
fi

echo
echo "===== PROVENANCE ====="
if [[ -f "$OUT/runtime_provenance.txt" ]]; then
  cat "$OUT/runtime_provenance.txt"
else
  echo "provenance not written"
fi

exit "$RC"
