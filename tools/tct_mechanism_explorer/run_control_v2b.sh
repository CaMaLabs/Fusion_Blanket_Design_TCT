#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
CONFIG="${CONFIG:-$HERE/explorer.control_v2b.json}"
M3D_ROOT="${M3D_ROOT:-/home/ubuntu/M3DC1-official}"
M3D_BUILD="${M3D_BUILD:-$M3D_ROOT/build-ubuntu-2d}"
EXE="${M3D_EXE:-$M3D_BUILD/unstructured/m3dc1_2d}"
POPULATION="${POPULATION:-8}"
GENERATIONS="${GENERATIONS:-4}"
SEED="${SEED:-8776}"
OUT="$REPO_ROOT/validation_runs/tct_control_architecture_v2b"

cd "$HERE"
mkdir -p "$OUT"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing config: $CONFIG" >&2
  exit 2
fi
if [[ ! -f "$M3D_ROOT/unstructured/input.f90" ]]; then
  echo "Missing M3D-C1 input source: $M3D_ROOT/unstructured/input.f90" >&2
  exit 2
fi
if ! grep -q 'add_var_int("ipforce"' "$M3D_ROOT/unstructured/input.f90"; then
  echo "This M3D-C1 checkout does not expose native ipforce." >&2
  exit 2
fi
if ! grep -q 'imag_control' "$M3D_ROOT/unstructured/input.f90"; then
  echo "The validated imag_control operator is not installed." >&2
  exit 2
fi

export TMPDIR="${TMPDIR:-/var/tmp}"
export OMPI_MCA_orte_tmpdir_base="$TMPDIR"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps

echo "=== TCT CONTROL ARCHITECTURE V2B ==="
echo "Mechanism-aware authority gate; V2 results are preserved separately."
echo "repo:        $REPO_ROOT"
echo "config:      $CONFIG"
echo "m3d:         $M3D_ROOT"
echo "build:       $M3D_BUILD"
echo "population:  $POPULATION"
echo "generations: $GENERATIONS"
echo "seed:        $SEED"
echo

echo "=== INSTALL/VERIFY STAGED MAGNETIC SELECTOR ==="
M3D_ROOT="$M3D_ROOT" M3D_BUILD="$M3D_BUILD" \
  python3 install_control_v2_operator.py all

if [[ ! -x "$EXE" ]]; then
  echo "Missing M3D-C1 executable after build: $EXE" >&2
  exit 2
fi

echo
echo "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

echo
echo "=== BOUNDED CANDIDATE DRY RUN ==="
python3 -m tct_explorer.cli dry-run \
  --config "$CONFIG" --count 8 --seed "$SEED" > "$OUT/dry_run.json"
echo "saved: $OUT/dry_run.json"

echo
echo "=== ZERO-ACTUATION EQUIVALENCE ==="
python3 -m tct_explorer.cli verify-zero \
  --config "$CONFIG" > "$OUT/zero_equivalence_stdout.json"
echo "saved: $OUT/zero_equivalence.json"

echo
echo "=== EVOLUTIONARY SEARCH ==="
python3 -m tct_explorer.cli search \
  --config "$CONFIG" \
  --population "$POPULATION" \
  --generations "$GENERATIONS" \
  --seed "$SEED" > "$OUT/pareto_stdout.json"

echo
echo "=== COMPACT RESULTS ==="
python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])

stats_path=root/'mechanism_stats.json'
front_path=root/'pareto_front.json'

if stats_path.exists():
    print('\nMECHANISM STATS')
    stats=json.loads(stats_path.read_text())
    for name,row in sorted(stats.items()):
        print(f"  {name:28s} count={row.get('count',0):3d}  impulse={row.get('impulse_authority',0):3d}  sustained={row.get('sustained',0):3d}  feasible={row.get('feasible',0):3d}")

if front_path.exists():
    print('\nPARETO FRONT (first 12)')
    front=json.loads(front_path.read_text())
    for item in front[:12]:
        c=item['candidate']
        stages=item.get('stages') or []
        s=stages[-1] if stages else {}
        m=s.get('metrics') or {}
        print(
            f"  {c['candidate_id']} {c['mechanism']:26s} "
            f"depth={item.get('deepest_stage')} feasible={item.get('feasible')} "
            f"W={m.get('mean_active_width_gain_pct')} "
            f"Jpk={m.get('mean_active_peak_j_change_pct')} "
            f"highJ={m.get('mean_active_high_j_change_pct')}"
        )
PY

echo
echo "=== COMPLETE ==="
echo "Results: $OUT"
echo "Full Pareto JSON is saved instead of flooding the terminal:"
echo "  $OUT/pareto_front.json"
echo "  $OUT/pareto_stdout.json"
echo "  $OUT/history.jsonl"
