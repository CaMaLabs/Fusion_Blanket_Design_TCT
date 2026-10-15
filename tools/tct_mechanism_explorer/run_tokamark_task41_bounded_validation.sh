#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec "${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}" tools/tct_mechanism_explorer/tokamark_102_validation.py
