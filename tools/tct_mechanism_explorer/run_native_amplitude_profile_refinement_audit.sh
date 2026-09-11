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

python3 -u tools/tct_mechanism_explorer/native_amplitude_profile_refinement_audit.py
RC=$?

OUT="validation_runs/m3dc1_tct_native_amplitude_profile_refinement"
SUMMARY="$OUT/native_profile_refinement_summary.json"

echo
if [[ -f "$SUMMARY" ]]; then
  echo "===== NATIVE AMPLITUDE/PROFILE RESULT ====="
  jq '{
    classification,
    sustained_pass_count,
    sustained_pass_cases,
    zero_equivalence_pass,
    best_case: (
      .best_case
      | {
          case,
          profile_width,
          drive_amp,
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
          max_high_J_time
        }
    )
  }' "$SUMMARY"

  echo
  echo "===== CASE RANKING ====="
  jq '[.case_summaries[] | {
    case,
    profile_width,
    drive_amp,
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
    max_high_J_change_pct,
    max_high_J_time
  }]' "$SUMMARY"

  echo
  echo "===== CURRENT-SAFE CASES ====="
  jq '[.case_summaries[]
    | select(.current_gate_pass_every_step_t0p10_to_t0p30 == true)
    | {
        case,
        profile_width,
        drive_amp,
        minimum_width_gain_pct,
        peak_width_gain_pct,
        final_width_gain_pct,
        worst_Jpk_change_pct,
        max_high_J_change_pct
      }
  ]' "$SUMMARY"

  echo
  echo "===== SUSTAINED PASS CASES ====="
  jq '[.case_summaries[]
    | select(.sustained_safe_authority == true)
    | {
        case,
        profile_width,
        drive_amp,
        minimum_width_gain_pct,
        worst_Jpk_change_pct,
        final_width_gain_pct,
        final_Jpk_change_pct,
        max_high_J_change_pct
      }
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

  echo
  echo "===== ZERO-EQUIVALENCE FAILURES ====="
  jq '[.zero_equivalence_by_width[] as $w
    | $w.checks[] as $t
    | $t.by_metric | to_entries[]
    | select(.value.pass == false)
    | {profile_width: $w.profile_width, time: $t.time, metric: .key, delta: .value.delta}
  ]' "$SUMMARY"
else
  echo "No summary produced."
  echo "Inspect:"
  echo "/tmp/m3dc1_tct_native_amplitude_profile_refinement_runs"
fi

echo
if [[ -f "$OUT/runtime_provenance.txt" ]]; then
  echo "===== PROVENANCE ====="
  cat "$OUT/runtime_provenance.txt"
fi

exit "$RC"
