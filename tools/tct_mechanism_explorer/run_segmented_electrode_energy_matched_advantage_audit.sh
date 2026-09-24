#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.venv-dudson/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
cd "$ROOT"
"$PY" tools/tct_mechanism_explorer/audit_segmented_electrode_energy_matched_advantage.py
