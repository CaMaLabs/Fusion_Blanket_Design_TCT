#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
CONFIG="${CONFIG:-$HERE/explorer.control_v2.json}"
M3D_ROOT="${M3D_ROOT:-/home/ubuntu/M3DC1-official}"
EXE="${M3D_EXE:-$M3D_ROOT/build-ubuntu-2d/unstructured/m3dc1_2d}"
POPULATION="${POPULATION:-8}"
GENERATIONS="${GENERATIONS:-4}"
SEED="${SEED:-8776}"

cd "$HERE"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing config: $CONFIG" >&2
  exit 2
fi
if [[ ! -x "$EXE" ]]; then
  echo "Missing M3D-C1 executable: $EXE" >&2
  exit 2
fi
if [[ ! -f "$M3D_ROOT/unstructured/input.f90" ]]; then
  echo "Missing M3D-C1 input source: $M3D_ROOT/unstructured/input.f90" >&2
  exit 2
fi
if ! grep -q 'add_var_int("ipforce"' "$M3D_ROOT/unstructured/input.f90"; then
  echo "This M3D-C1 checkout does not expose the native ipforce poloidal momentum source." >&2
  exit 2
fi
if ! grep -q 'imag_control' "$M3D_ROOT/unstructured/input.f90"; then
  echo "The previously validated imag_control input is not installed in this M3D-C1 checkout." >&2
  echo "Run the existing magnetic-operator installer/pulse-train install step first." >&2
  exit 2
fi

export TMPDIR="${TMPDIR:-/var/tmp}"
export OMPI_MCA_orte_tmpdir_base="$TMPDIR"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps

echo "=== TCT CONTROL ARCHITECTURE V2 ==="
echo "repo:        $REPO_ROOT"
echo "config:      $CONFIG"
echo "m3d:         $M3D_ROOT"
echo "executable:  $EXE"
echo "population:  $POPULATION"
echo "generations: $GENERATIONS"
echo "seed:        $SEED"
echo

echo "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

echo
echo "=== BOUNDED CANDIDATE DRY RUN ==="
python3 -m tct_explorer.cli dry-run --config "$CONFIG" --count 6 --seed "$SEED"

echo
echo "=== ZERO-ACTUATION EQUIVALENCE ==="
python3 -m tct_explorer.cli verify-zero --config "$CONFIG"

echo
echo "=== EVOLUTIONARY SEARCH ==="
python3 -m tct_explorer.cli search \
  --config "$CONFIG" \
  --population "$POPULATION" \
  --generations "$GENERATIONS" \
  --seed "$SEED"

echo
echo "=== COMPLETE ==="
echo "Results: $REPO_ROOT/validation_runs/tct_control_architecture_v2"
echo "Inspect:"
echo "  cat $REPO_ROOT/validation_runs/tct_control_architecture_v2/mechanism_stats.json"
echo "  cat $REPO_ROOT/validation_runs/tct_control_architecture_v2/pareto_front.json"
echo "  tail -n 5 $REPO_ROOT/validation_runs/tct_control_architecture_v2/history.jsonl"
