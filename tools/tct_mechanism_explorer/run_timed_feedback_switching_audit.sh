#!/usr/bin/env bash
set -euo pipefail

REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"

SWEEP_TMP="${TCT_MPI_TMPDIR:-/tmp/tct-$USER}"
mkdir -p "$SWEEP_TMP"
export TMPDIR="$SWEEP_TMP"
export OMPI_MCA_orte_tmpdir_base="$SWEEP_TMP"
mkdir -p "$TMPDIR" "$OMPI_MCA_orte_tmpdir_base"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps

# Compatibility shim for native_feedback_controller_audit.py on this branch.
# It preserves literal Bash ${...} expansions embedded inside that module's
# Python f-string launcher without changing audit inputs or M3D-C1 physics.
python3 - "$REPO/tools/tct_mechanism_explorer/timed_feedback_switching_audit.py" <<'PY'
import builtins
import runpy
import sys
from pathlib import Path


class _LiteralShellParameter:
    def __init__(self, name: str) -> None:
        self.name = name

    def __format__(self, spec: str) -> str:
        return "{" + self.name + ":" + spec + "}"


builtins.TMPDIR = _LiteralShellParameter("TMPDIR")
builtins.OMPI_MCA_orte_tmpdir_base = _LiteralShellParameter(
    "OMPI_MCA_orte_tmpdir_base"
)

audit = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(audit.parent))
runpy.run_path(str(audit), run_name="__main__")
PY

OUT="validation_runs/m3dc1_tct_timed_feedback_switching"
SUMMARY="$OUT/timed_feedback_summary.json"

echo
echo "===== TIMED + FEEDBACK RESULT ====="
jq '{
  classification,
  zero_equivalence,
  best_case: (
    .best_case | {
      case,
      kind,
      peak_width_gain_pct,
      peak_time,
      sustained_positive_from_t0p10,
      current_gate_pass_late,
      late_reversal_detected,
      final_width_gain_pct,
      final_Jpk_change_pct,
      final_safe_authority
    }
  ),
  feedback_case: (
    .feedback_case | {
      peak_width_gain_pct,
      peak_time,
      sustained_positive_from_t0p10,
      current_gate_pass_late,
      late_reversal_detected,
      final_width_gain_pct,
      final_Jpk_change_pct,
      final_safe_authority
    }
  )
}' "$SUMMARY"

echo
echo "===== TOP CASES ====="
jq '[.case_summaries[:12][] | {
  case,
  kind,
  peak_width_gain_pct,
  peak_time,
  width_gate_pass_any,
  sustained_positive_from_t0p10,
  current_gate_pass_late,
  late_reversal_detected,
  final_width_gain_pct,
  final_Jpk_change_pct,
  final_safe_authority
}]' "$SUMMARY"

echo
echo "===== FEEDBACK COMMAND HISTORY ====="
jq '[.feedback_case.command_history[] | {
  step,
  start,
  stop,
  state,
  amp,
  width_gain_pct,
  Jpk_change_pct,
  delta_Jint_high_abs,
  high_J_change_pct,
  reason_for_next_state,
  next_state
}]' "$SUMMARY"

echo
echo "===== HIGH-J ABSOLUTE DIAGNOSTICS ====="
jq '[
  .case_summaries[] as $c
  | $c.samples[]
  | select(.time == 0.15 or .time == 0.20 or .time == 0.30)
  | {
      case: $c.case,
      time,
      baseline_Jint_high,
      controlled_Jint_high,
      delta_Jint_high_abs,
      high_J_change_pct
    }
] | .[:30]' "$SUMMARY"

echo
echo "===== PROVENANCE ====="
cat "$OUT/runtime_provenance.txt"
