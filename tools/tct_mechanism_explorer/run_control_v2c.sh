#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONFIG="${CONFIG:-$HERE/explorer.control_v2c.json}"
export OUT="${OUT:-$(cd "$HERE/../.." && pwd)/validation_runs/tct_control_architecture_v2c}"
export RUN_LABEL="TCT CONTROL ARCHITECTURE V2C — SUSTAINMENT AND ABLATION"
export POPULATION="${POPULATION:-6}"
export GENERATIONS="${GENERATIONS:-1}"
exec "$HERE/run_control_v2b.sh"
