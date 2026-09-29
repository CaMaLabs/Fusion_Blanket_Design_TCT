#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

exec python3 \
    tools/tct_mechanism_explorer/run_segmented_electrode_bout_runtime_evidence_probe.py
