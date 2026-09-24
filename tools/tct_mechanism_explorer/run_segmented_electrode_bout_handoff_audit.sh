#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tools/tct_mechanism_explorer/audit_bout_segmented_electrode_handoff.py
