#!/usr/bin/env bash
set -uo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
cd "$REPO" || exit 96
PY="${TCT_AUDIT_PYTHON:-python3}"
"$PY" -u tools/tct_mechanism_explorer/native_magnetic_probe_enablement_audit.py
