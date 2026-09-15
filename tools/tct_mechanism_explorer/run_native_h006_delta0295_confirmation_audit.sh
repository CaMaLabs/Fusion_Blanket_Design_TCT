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

python3 -u tools/tct_mechanism_explorer/native_h006_delta0295_confirmation_audit.py
RC=$?

OUT="validation_runs/m3dc1_tct_native_h006_delta0295_confirmation"
SUMMARY="$OUT/preemptive_timing_amplitude_refinement_summary.json"

if [[ -f "$SUMMARY" ]]; then
  echo "===== NATIVE h=0.06 DELTA=0.295 CONFIRMATION ====="
  jq '{classification, sustained_pass_count, sustained_pass_cases, current_safe_count, current_safe_cases,
       zero_equivalence_pass: .zero_equivalence.pass,
       handoff_equivalence_pass: .handoff_equivalence.pass,
       best_case: (.best_case | {case, first_amp, second_amp, second_start,
         sustained_safe_authority, continuous_positive_width_t0p10_to_t0p30,
         current_gate_pass_every_step_t0p10_to_t0p30, width_gate_pass_any,
         minimum_width_gain_pct, minimum_width_time, peak_width_gain_pct, peak_width_time,
         worst_Jpk_change_pct, worst_Jpk_time, Jpk_guard_margin_pct,
         final_width_gain_pct, final_Jpk_change_pct,
         t0p14_width_gain_pct, t0p14_Jpk_change_pct,
         t0p15_width_gain_pct, t0p15_Jpk_change_pct,
         t0p16_width_gain_pct, t0p16_Jpk_change_pct})}' "$SUMMARY"
else
  echo "No summary produced."
fi

exit "$RC"
