#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
exec "${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}" tools/tct_mechanism_explorer/diiid_efit_native_handoff_108.py
