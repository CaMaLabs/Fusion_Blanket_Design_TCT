from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from .mechanisms import candidate_updates
from .models import Candidate

COPY_NAMES=["circle-0.10-0.0-0.0-1K0.smb","circle-0.10-0.0-0.0.txt","part0.smb","part.smb"]

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def replace_or_add(text: str, key: str, value: Any) -> str:
    pattern=re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$",re.M); rendered=str(value).lower() if isinstance(value,bool) else str(value)
    if pattern.search(text): return pattern.sub(rf"\g<1>{rendered}",text)
    marker="\n /\n"
    if marker not in text: raise RuntimeError(f"C1input namelist terminator not found while adding {key}")
    return text.replace(marker,f"\n {key} = {rendered}\n /\n",1)

class M3DRunner:
    def __init__(self,cfg:dict[str,Any])->None:
        self.cfg=cfg; p=cfg["paths"]; self.baseline=Path(p["baseline_dir"]); self.executable=Path(p["executable"]); self.run_root=Path(p["run_root"])
    def _copy_baseline_assets(self,run_dir:Path)->None:
        for name in COPY_NAMES:
            src=self.baseline/name
            if not src.exists() and not src.is_symlink(): continue
            dst=run_dir/name
            if src.is_symlink(): dst.symlink_to(src.readlink())
            else: shutil.copy2(src,dst)
    def prepare(self,candidate:Candidate,stage:str,overwrite:bool=True)->tuple[Path,dict[str,Any]]:
        run_dir=self.run_root/candidate.candidate_id/stage
        if overwrite and run_dir.exists(): shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True,exist_ok=True); self._copy_baseline_assets(run_dir)
        base_input=self.baseline/"C1input"
        if not base_input.exists(): raise FileNotFoundError(base_input)
        updates=candidate_updates(candidate,stage,self.cfg); text=base_input.read_text(encoding="utf-8")
        for key,value in updates.items(): text=replace_or_add(text,key,value)
        input_path=run_dir/"C1input"; input_path.write_text(text,encoding="utf-8")
        manifest={"candidate":candidate.to_dict(),"stage":stage,"updates":updates,"baseline":str(self.baseline),"executable":str(self.executable),"input_sha256":sha256_file(input_path)}
        (run_dir/"candidate_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        rt=self.cfg["runtime"]; extra=" ".join(str(x) for x in rt["mpirun_extra"]); petsc=" ".join(str(x) for x in rt["petsc_args"])
        launch=f'''#!/usr/bin/env bash
set -euo pipefail
export TMPDIR={rt["tmpdir"]}
export OMPI_MCA_orte_tmpdir_base={rt["tmpdir"]}
source "{rt["spack_setup"]}"
spack env activate {rt["spack_env"]}
cd "{run_dir}"
set +e
timeout {int(rt["timeout_seconds"])}s mpirun {extra} -n {int(rt["mpi_ranks"])} "{self.executable}" {petsc} > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\n' "$rc" > run_status.txt
exit "$rc"
'''
        launch_path=run_dir/"launch_command.sh"; launch_path.write_text(launch,encoding="utf-8"); launch_path.chmod(0o755)
        return run_dir,manifest
    def execute(self,candidate:Candidate,stage:str)->tuple[int,Path,dict[str,Any],float]:
        run_dir,manifest=self.prepare(candidate,stage); started=time.time(); p=subprocess.run(["bash",str(run_dir/"launch_command.sh")],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT); elapsed=time.time()-started
        (run_dir/"launcher_wrapper_stdout.log").write_text(p.stdout or "",encoding="utf-8")
        return p.returncode,run_dir,manifest,elapsed
