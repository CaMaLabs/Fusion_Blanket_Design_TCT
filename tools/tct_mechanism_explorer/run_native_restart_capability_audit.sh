#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
M3DC1_ROOT="${M3DC1_ROOT:-/home/ubuntu/M3DC1-official}"
cd "$REPO"
OUTDIR="validation_runs/m3dc1_tct_native_restart_capability"
OUT="$OUTDIR/native_restart_capability_summary.json"
mkdir -p "$OUTDIR"

if [[ ! -d "$M3DC1_ROOT" ]]; then
  echo "ERROR: native M3D-C1 root not found: $M3DC1_ROOT"
  exit 96
fi

# This is a capability/provenance audit only. It does not alter solver physics or
# authorize a long-horizon efficacy matrix. Search the installed native tree for
# restart/checkpoint interfaces that could make the physically calibrated horizon
# reachable without a 60,899x monolithic extension.
MATCHES="$OUTDIR/restart_matches.txt"
find "$M3DC1_ROOT" -type f \( -name '*.f' -o -name '*.f90' -o -name '*.F' -o -name '*.F90' -o -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.in' -o -name '*.txt' -o -name '*.md' \) -print0 2>/dev/null \
  | xargs -0 grep -Ein 'restart|checkpoint|resume|read.*state|write.*state|C1\.h5|hdf5' 2>/dev/null \
  | head -n 500 > "$MATCHES" || true

COUNT=$(wc -l < "$MATCHES" | tr -d ' ')
if [[ "$COUNT" -gt 0 ]]; then
  CLASS="M3DC1_TCT_NATIVE_RESTART_CAPABILITY_CANDIDATES_FOUND_REQUIRES_VALIDATION"
  DECISION="Restart/checkpoint candidates exist in the installed native M3D-C1 tree. Validate one candidate with a short split-run versus continuous-run state-equivalence audit before any long physically timed controller run."
else
  CLASS="M3DC1_TCT_NATIVE_RESTART_CAPABILITY_NOT_FOUND_BY_STATIC_AUDIT"
  DECISION="No restart/checkpoint interface was identified by the bounded static audit. Do not brute-force the 60,899x horizon; next work must establish a physically relevant event/window or independently documented restart/time-scaling path."
fi

python3 - "$OUT" "$MATCHES" "$COUNT" "$CLASS" "$DECISION" "$M3DC1_ROOT" <<'PY'
import json, pathlib, sys
out, matches, count, classification, decision, root = sys.argv[1:]
lines = pathlib.Path(matches).read_text(errors='replace').splitlines()
data = {
  "classification": classification,
  "pipeline_failure": False,
  "parent_job_id": "20260917-016-native-precursor-horizon-reachability",
  "parent_classification": "M3DC1_TCT_NATIVE_PRECURSOR_HORIZON_DIRECT_EXTENSION_IMPRACTICAL",
  "audit_scope": "Static capability/provenance audit of installed native M3D-C1 tree; no controller-efficacy run.",
  "m3dc1_root": root,
  "restart_candidate_match_count": int(count),
  "restart_candidate_excerpt": lines[:40],
  "zero_equivalence_status": "NOT_EVALUATED_CAPABILITY_AUDIT_ONLY",
  "frozen_gates": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.1},
  "precursor_authority": "Mirnov/toroidal; reduced-model proxies are not substituted",
  "claim_boundary": "Normalized native M3D-C1 capability/provenance only; no controller-efficacy, reactor-scale, or experimental stabilization claim.",
  "decision": decision,
}
pathlib.Path(out).write_text(json.dumps(data, indent=2) + "\n")
PY

echo "===== NATIVE M3D-C1 RESTART CAPABILITY AUDIT ====="
jq '{classification,pipeline_failure,parent_classification,restart_candidate_match_count,zero_equivalence_status,frozen_gates,claim_boundary,decision}' "$OUT"
