#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR="/tmp/tct-${USER:-ubuntu}"
export OMPI_MCA_orte_tmpdir_base="$TMPDIR"
mkdir -p "$TMPDIR"
python3 -u tools/tct_mechanism_explorer/native_restart_full_precision_handoff_repair.py
