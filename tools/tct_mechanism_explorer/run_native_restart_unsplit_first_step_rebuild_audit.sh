#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"
python3 -u tools/tct_mechanism_explorer/native_restart_unsplit_first_step_rebuild_audit.py
