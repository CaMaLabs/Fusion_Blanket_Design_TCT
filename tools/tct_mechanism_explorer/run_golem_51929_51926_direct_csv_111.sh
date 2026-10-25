#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
exec "${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}" tools/tct_mechanism_explorer/golem_51929_51926_direct_csv_111.py
