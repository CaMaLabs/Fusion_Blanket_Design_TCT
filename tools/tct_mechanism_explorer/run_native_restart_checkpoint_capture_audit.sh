#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
SWEEP_TMP="${TCT_MPI_TMPDIR:-/tmp/tct-$USER}"
mkdir -p "$SWEEP_TMP"
export TMPDIR="$SWEEP_TMP"
export OMPI_MCA_orte_tmpdir_base="$SWEEP_TMP"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 -u tools/tct_mechanism_explorer/native_restart_checkpoint_capture_audit.py
