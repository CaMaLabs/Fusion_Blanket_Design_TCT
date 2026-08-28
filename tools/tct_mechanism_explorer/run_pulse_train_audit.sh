#!/usr/bin/env bash
set -euo pipefail

REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"

source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp

python3 tools/tct_mechanism_explorer/pulse_train_audit.py all

echo
echo "Pulse-train summary:"
cat validation_runs/m3dc1_tct_magnetic_pulse_train/pulse_train_summary.json
