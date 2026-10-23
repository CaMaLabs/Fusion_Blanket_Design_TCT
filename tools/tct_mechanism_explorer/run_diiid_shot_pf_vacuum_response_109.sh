#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
exec "${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}" tools/tct_mechanism_explorer/diiid_shot_pf_vacuum_response_109.py
