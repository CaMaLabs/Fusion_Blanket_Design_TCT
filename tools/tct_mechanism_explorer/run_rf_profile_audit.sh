#!/usr/bin/env bash
set -euo pipefail

REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp

python3 tools/tct_mechanism_explorer/rf_profile_audit.py

echo
echo "RF-profile summary:"
cat validation_runs/m3dc1_tct_rf_profile/rf_profile_summary.json
