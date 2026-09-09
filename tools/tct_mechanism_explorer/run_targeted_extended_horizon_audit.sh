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
# It emits Bash parameter expansion from a Python f-string; these formatter
# objects preserve the literal shell ${...} fields without changing M3D-C1
# inputs, actuator parameters, or audit physics.
python3 - "$REPO/tools/tct_mechanism_explorer/targeted_extended_horizon_audit.py" <<'PY'
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

OUT="validation_runs/m3dc1_tct_targeted_extended_horizon"
SUMMARY="$OUT/targeted_extended_horizon_summary.json"

echo
echo "===== TARGETED EXTENDED-HORIZON RESULT ====="
jq '{
  classification,
  best_point_candidate,
  best_sustained_candidate,
  confirmation: {
    target: .confirmation.target,
    repeat_count: .confirmation.repeat_count,
    max_abs_repeat_delta: .confirmation.max_abs_repeat_delta
  }
}' "$SUMMARY"

echo
echo "===== TOP CASE SUMMARIES ====="
jq '[.case_summaries[:12][] | {
  case,
  W_cd,
  amp,
  peak_width_gain_pct,
  peak_time,
  width_gate_pass_any,
  current_gate_pass_all,
  desired_redistribution_signature_at_peak,
  sustained_positive_from_t0p10,
  late_reversal_detected,
  sustained_safe_authority
}]' "$SUMMARY"

echo
echo "===== ZERO-EQUIVALENCE FAILURES ====="
jq '[
  .zero_equivalence
  | to_entries[]
  | select(.value.pass == false)
]' "$SUMMARY"

echo
echo "===== PROVENANCE ====="
cat "$OUT/runtime_provenance.txt"
