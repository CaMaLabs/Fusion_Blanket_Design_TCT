#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR="${TMPDIR:-/tmp/tct-$USER}"
export OMPI_MCA_orte_tmpdir_base="$TMPDIR"
python3 tools/tct_mechanism_explorer/native_feedback_polarity_124.py
