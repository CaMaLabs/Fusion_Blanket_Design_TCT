#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 -u tools/tct_mechanism_explorer/native_restart_checkpoint_link_consistency_audit.py
