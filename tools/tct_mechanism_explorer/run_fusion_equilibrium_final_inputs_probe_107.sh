#!/usr/bin/env bash
set -euo pipefail
cd "${TCT_PIPELINE_REPO:-$(git rev-parse --show-toplevel)}"
PY="${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}"
"$PY" - <<'PY'
import importlib.util,subprocess,sys
if importlib.util.find_spec("datasets") is None:
    subprocess.check_call([sys.executable,"-m","pip","install","--disable-pip-version-check","datasets>=3,<5"])
PY
exec "$PY" tools/tct_mechanism_explorer/run_fusion_equilibrium_challenge_tct_intake.py
