#!/usr/bin/env bash
set -euo pipefail

REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp

python3 tools/tct_mechanism_explorer/native_feedback_controller_audit.py

echo
echo "Native feedback summary:"
cat validation_runs/m3dc1_tct_native_feedback/native_feedback_summary.json
