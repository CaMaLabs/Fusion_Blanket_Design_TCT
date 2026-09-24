#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
cd "$REPO"
"$PY" tools/tct_mechanism_explorer/audit_segmented_electrode_spatial_identifiability.py
