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

python3 -u tools/tct_mechanism_explorer/native_two_profile_handoff_audit.py
RC=$?

OUT="validation_runs/m3dc1_tct_native_two_profile_handoff"
SUMMARY="$OUT/native_two_profile_handoff_summary.json"

echo
if [[ -f "$SUMMARY" ]]; then
  echo "===== NATIVE TWO-PROFILE HANDOFF RESULT ====="
  jq '{
    classification,
    sustained_pass_count,
    sustained_pass_cases,
    current_safe_count,
    current_safe_cases,
    zero_equivalence_pass: .zero_equivalence.pass,
    handoff_equivalence_pass: .handoff_equivalence.pass,
    best_case: (
      .best_case | {
        case,
        second_start,
        second_shoulder_width,
        second_shoulder_delta,
        sustained_safe_authority,
        continuous_positive_width_t0p10_to_t0p30,
        current_gate_pass_every_step_t0p10_to_t0p30,
        width_gate_pass_any,
        final_width_gate_pass,
        minimum_width_gain_pct,
        minimum_width_time,
        peak_width_gain_pct,
        peak_width_time,
        worst_Jpk_change_pct,
        worst_Jpk_time,
        Jpk_guard_margin_pct,
        final_width_gain_pct,
        final_Jpk_change_pct,
        max_high_J_change_pct,
        max_high_J_time,
        t0p13_width_gain_pct,
        t0p13_Jpk_change_pct,
        t0p14_width_gain_pct,
        t0p14_Jpk_change_pct,
        t0p15_width_gain_pct,
        t0p15_Jpk_change_pct,
        t0p16_width_gain_pct,
        t0p16_Jpk_change_pct
      }
    )
  }' "$SUMMARY"

  echo
  echo "===== CASE RANKING ====="
  jq '[.case_summaries[] | {
    case,
    second_start,
    second_shoulder_width,
    second_shoulder_delta,
    sustained_safe_authority,
    continuous_positive_width_t0p10_to_t0p30,
    current_gate_pass_every_step_t0p10_to_t0p30,
    final_width_gate_pass,
    minimum_width_gain_pct,
    minimum_width_time,
    peak_width_gain_pct,
    peak_width_time,
    worst_Jpk_change_pct,
    worst_Jpk_time,
    Jpk_guard_margin_pct,
    final_width_gain_pct,
    final_Jpk_change_pct,
    max_high_J_change_pct
  }]' "$SUMMARY"

  echo
  echo "===== CURRENT-SAFE CASES ====="
  jq '[.case_summaries[]
    | select(.current_gate_pass_every_step_t0p10_to_t0p30 == true)
    | {
        case,
        second_start,
        second_shoulder_width,
        second_shoulder_delta,
        minimum_width_gain_pct,
        peak_width_gain_pct,
        final_width_gain_pct,
        worst_Jpk_change_pct
      }
  ]' "$SUMMARY"

  echo
  echo "===== SAFE THROUGH t=0.16 ====="
  jq '[.case_summaries[]
    | select(
        .t0p14_Jpk_change_pct <= 0.10 and
        .t0p14_width_gain_pct > 0 and
        .t0p15_Jpk_change_pct <= 0.10 and
        .t0p15_width_gain_pct > 0 and
        .t0p16_Jpk_change_pct <= 0.10 and
        .t0p16_width_gain_pct > 0
      )
    | {
        case,
        second_start,
        second_shoulder_width,
        second_shoulder_delta,
        t0p14_width_gain_pct,
        t0p14_Jpk_change_pct,
        t0p15_width_gain_pct,
        t0p15_Jpk_change_pct,
        t0p16_width_gain_pct,
        t0p16_Jpk_change_pct,
        final_width_gain_pct
      }
  ]' "$SUMMARY"

  echo
  echo "===== SUSTAINED PASS CASES ====="
  jq '[.case_summaries[]
    | select(.sustained_safe_authority == true)
    | {
        case,
        second_start,
        second_shoulder_width,
        second_shoulder_delta,
        minimum_width_gain_pct,
        worst_Jpk_change_pct,
        final_width_gain_pct,
        final_Jpk_change_pct
      }
  ]' "$SUMMARY"

  echo
  echo "===== HANDOFF-EQUIVALENCE FAILURES ====="
  jq '[.handoff_equivalence.checks[] as $t
    | $t.by_metric | to_entries[]
    | select(.value.pass == false)
    | {time: $t.time, metric: .key, delta: .value.delta}
  ]' "$SUMMARY"

  echo
  echo "===== ZERO-EQUIVALENCE FAILURES ====="
  jq '[.zero_equivalence.checks[] as $t
    | $t.by_metric | to_entries[]
    | select(.value.pass == false)
    | {time: $t.time, metric: .key, delta: .value.delta}
  ]' "$SUMMARY"

  echo
  echo "===== BEST CASE EVERY-STEP TRAJECTORY ====="
  jq '.best_case.all_step_samples | map({
    time,
    width_gain_pct,
    Jpk_change_pct,
    high_J_change_pct,
    delta_Jint_high_abs
  })' "$SUMMARY"
else
  echo "No summary produced."
  echo "Inspect /tmp/m3dc1_tct_native_two_profile_handoff_runs"
fi

echo
if [[ -f "$OUT/runtime_provenance.txt" ]]; then
  echo "===== PROVENANCE ====="
  cat "$OUT/runtime_provenance.txt"
fi

exit "$RC"
