#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR="${TMPDIR:-/var/tmp}"

CONFIG="${1:-explorer.json}"
POPULATION="${POPULATION:-8}"
GENERATIONS="${GENERATIONS:-4}"
SEED="${SEED:-8776}"

if [[ ! -f "$CONFIG" ]]; then
  python3 -m tct_explorer.cli init --output "$CONFIG"
fi

python3 -m unittest discover -s tests -v
python3 -m tct_explorer.cli verify-zero --config "$CONFIG"
python3 -m tct_explorer.cli search \
  --config "$CONFIG" \
  --population "$POPULATION" \
  --generations "$GENERATIONS" \
  --seed "$SEED"
