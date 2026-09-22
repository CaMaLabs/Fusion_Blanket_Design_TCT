#!/usr/bin/env bash
set -euo pipefail

REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO"

python3 -u tools/tct_mechanism_explorer/audit_native_magnetic_probe_placement.py
