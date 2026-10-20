#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="${TCT_PYTHON:-$PWD/.venv-dudson/bin/python}"
"$PY" - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("numcodecs") is None:
    print("INFRASTRUCTURE: installing pinned numcodecs==0.16.3 into canonical research venv",flush=True)
    subprocess.check_call([sys.executable,"-m","pip","install","--disable-pip-version-check","numcodecs==0.16.3"])
import numcodecs
print("numcodecs",numcodecs.__version__,flush=True)
PY
"$PY" tools/tct_mechanism_explorer/tokamark_102_validation.py
"$PY" - <<'PY'
import json, shutil
from pathlib import Path
source=Path("validation_runs/tokamark_task41_bounded_validation/summary.json")
dest=Path("validation_runs/tokamark_task41_decode_alignment_103")
dest.mkdir(parents=True,exist_ok=True)
data=json.loads(source.read_text())
data["job_id"]="20261019-103-tokamark-task41-decode-and-time-alignment"
data["rerun_of"]="20261014-102-tokamark-task41-bounded-waveform-validation"
(dest/"summary.json").write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
print(json.dumps({"classification":data["classification"],"decoded_pairs":data.get("valid_time_signal_pairs",[]),"errors":data.get("errors",[])}))
PY
