#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
M3DC1_ROOT="${M3DC1_ROOT:-/home/ubuntu/M3DC1-official}"
cd "$REPO"
OUTDIR="validation_runs/m3dc1_tct_native_restart_interface_specificity"
OUT="$OUTDIR/native_restart_interface_specificity_summary.json"
mkdir -p "$OUTDIR"

if [[ ! -d "$M3DC1_ROOT" ]]; then
  echo "ERROR: native M3D-C1 root not found: $M3DC1_ROOT"
  exit 96
fi

# The preceding broad audit found many HDF5/build-system hits. This audit deliberately
# narrows to runtime/source interfaces that could actually resume solver state. It does
# not execute a restart and does not make a controller-efficacy claim.
SRC="$OUTDIR/runtime_restart_source_matches.txt"
CFG="$OUTDIR/runtime_restart_config_matches.txt"
: > "$SRC"; : > "$CFG"
find "$M3DC1_ROOT" -type f \( -name '*.f' -o -name '*.f90' -o -name '*.F' -o -name '*.F90' -o -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) -print0 2>/dev/null \
 | xargs -0 grep -Ein '\b(restart|checkpoint|resume)\b|read[^[:alnum:]_]*(restart|checkpoint|state)|write[^[:alnum:]_]*(restart|checkpoint|state)' 2>/dev/null \
 | grep -Eiv '/(CMakeFiles|build[^/]*)/' | head -n 300 > "$SRC" || true
find "$M3DC1_ROOT" -type f \( -name '*.in' -o -name '*.nml' -o -name '*.namelist' -o -name '*.txt' -o -name '*.md' \) -print0 2>/dev/null \
 | xargs -0 grep -Ein '\b(restart|checkpoint|resume)\b' 2>/dev/null \
 | grep -Eiv '/(CMakeFiles|build[^/]*)/' | head -n 200 > "$CFG" || true

SRC_COUNT=$(wc -l < "$SRC" | tr -d ' ')
CFG_COUNT=$(wc -l < "$CFG" | tr -d ' ')
if [[ "$SRC_COUNT" -gt 0 || "$CFG_COUNT" -gt 0 ]]; then
  CLASS="M3DC1_TCT_NATIVE_RESTART_INTERFACE_HIGH_SIGNAL_CANDIDATES_FOUND_REQUIRES_SPLIT_RUN_VALIDATION"
  DECISION="High-signal runtime restart/checkpoint candidates remain after excluding generic HDF5/build hits. Inspect the recorded source/config interfaces and validate one with a short continuous-versus-split native state-equivalence run before using restart for precursor-horizon work."
else
  CLASS="M3DC1_TCT_NATIVE_RESTART_INTERFACE_NOT_ESTABLISHED_BY_SPECIFICITY_AUDIT"
  DECISION="The broad restart audit was not sufficient evidence of a usable runtime restart path: no high-signal runtime/source interface survived this specificity audit. Do not infer restart capability from HDF5 linkage alone and do not authorize the long precursor-horizon run."
fi

python3 - "$OUT" "$SRC" "$CFG" "$SRC_COUNT" "$CFG_COUNT" "$CLASS" "$DECISION" "$M3DC1_ROOT" <<'PY'
import json, pathlib, sys
out, src, cfg, ns, nc, classification, decision, root = sys.argv[1:]
src_lines = pathlib.Path(src).read_text(errors='replace').splitlines()
cfg_lines = pathlib.Path(cfg).read_text(errors='replace').splitlines()
data = {
  "classification": classification,
  "pipeline_failure": False,
  "parent_job_id": "20260917-017-native-restart-capability-audit",
  "parent_classification": "M3DC1_TCT_NATIVE_RESTART_CAPABILITY_CANDIDATES_FOUND_REQUIRES_VALIDATION",
  "audit_scope": "High-specificity static runtime restart-interface audit; no controller-efficacy run and no restart execution.",
  "m3dc1_root": root,
  "runtime_source_match_count": int(ns),
  "runtime_config_match_count": int(nc),
  "runtime_source_excerpt": src_lines[:40],
  "runtime_config_excerpt": cfg_lines[:30],
  "zero_equivalence_status": "NOT_EVALUATED_CAPABILITY_AUDIT_ONLY",
  "handoff_equivalence_status": "NOT_EVALUATED_NO_RESTART_EXECUTED",
  "frozen_gates": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.1},
  "precursor_authority": "Mirnov/toroidal; reduced-model proxies are not substituted",
  "claim_boundary": "Normalized native M3D-C1 capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.",
  "decision": decision,
}
pathlib.Path(out).write_text(json.dumps(data, indent=2) + "\n")
PY

jq '{classification,pipeline_failure,runtime_source_match_count,runtime_config_match_count,zero_equivalence_status,handoff_equivalence_status,frozen_gates,claim_boundary,decision}' "$OUT"
