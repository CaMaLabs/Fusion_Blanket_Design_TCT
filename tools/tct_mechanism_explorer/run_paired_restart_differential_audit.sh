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

python3 tools/tct_mechanism_explorer/paired_restart_differential_audit.py
RC=$?

OUT="validation_runs/m3dc1_tct_paired_restart_differential"
SUMMARY="$OUT/paired_restart_summary.json"

echo
if [[ -f "$SUMMARY" ]]; then
  echo "===== PAIRED-RESTART DIFFERENTIAL RESULT ====="
  jq '{
    classification,
    best_case: (
      .best_case
      | {
          case,
          kind,
          peak_width_gain_pct,
          peak_time,
          safe_gate_pass_any,
          sustained_positive_from_t0p10,
          current_gate_pass_late,
          late_reversal_detected,
          final_width_gain_pct,
          final_Jpk_change_pct,
          final_safe_authority,
          max_abs_paired_null_restart_bias_width_pct
        }
    ),
    feedback_case: (
      .feedback_case
      | {
          peak_width_gain_pct,
          peak_time,
          safe_gate_pass_any,
          sustained_positive_from_t0p10,
          current_gate_pass_late,
          late_reversal_detected,
          final_width_gain_pct,
          final_Jpk_change_pct,
          final_safe_authority,
          max_abs_paired_null_restart_bias_width_pct
        }
    )
  }' "$SUMMARY"

  echo
  echo "===== CASE RANKING ====="
  jq '[.case_summaries[] | {
    case,
    kind,
    peak_width_gain_pct,
    peak_time,
    safe_gate_pass_any,
    sustained_positive_from_t0p10,
    current_gate_pass_late,
    late_reversal_detected,
    final_width_gain_pct,
    final_Jpk_change_pct,
    final_safe_authority,
    max_abs_paired_null_restart_bias_width_pct
  }]' "$SUMMARY"

  echo
  echo "===== SAFE GATE SAMPLES ====="
  jq '[.case_summaries[] as $case
    | $case.samples[]
    | select(.width_gate_pass == true and .current_gate_pass == true)
    | {
        case: $case.case,
        time,
        width_gain_pct,
        Jpk_change_pct,
        high_J_change_pct,
        delta_Jint_high_abs,
        paired_null_restart_bias_width_pct
      }
  ]' "$SUMMARY"

  echo
  echo "===== FEEDBACK COMMAND HISTORY ====="
  jq '[.feedback_case.command_history[] | {
    step,
    start,
    stop,
    state,
    amp,
    next_state,
    reason_for_next_state,
    width_gain_pct,
    Jpk_change_pct,
    high_J_change_pct,
    paired_null_restart_bias_width_pct
  }]' "$SUMMARY"

  echo
  echo "===== RESTART-BIAS DIAGNOSTIC ====="
  jq '[.case_summaries[] as $case
    | $case.samples[]
    | {
        case: $case.case,
        time,
        paired_null_restart_bias_width_pct,
        paired_null_restart_bias_Jpk_pct
      }
  ]' "$SUMMARY"
else
  echo "No summary produced. Check the most recent control/null segment logs under:"
  echo "/tmp/m3dc1_tct_paired_restart_differential_runs"
fi

echo
if [[ -f "$OUT/runtime_provenance.txt" ]]; then
  echo "===== PROVENANCE ====="
  cat "$OUT/runtime_provenance.txt"
fi

exit "$RC"
