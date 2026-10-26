#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
exec "${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}" tools/tct_mechanism_explorer/tcv_fenix_zenodo_archive_index_113.py
