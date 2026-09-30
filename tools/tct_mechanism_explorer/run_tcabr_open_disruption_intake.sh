#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec python3 tools/tct_mechanism_explorer/run_tcabr_open_disruption_intake.py
