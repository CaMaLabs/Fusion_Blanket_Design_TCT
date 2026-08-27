from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Candidate, Evaluation, StageResult

class Store:
    def __init__(self,output_dir:str|Path)->None:
        self.root=Path(output_dir);self.root.mkdir(parents=True,exist_ok=True);self.history=self.root/"history.jsonl";self.checkpoint=self.root/"checkpoint.json"
    def append(self,evaluation:Evaluation)->None:
        with self.history.open("a",encoding="utf-8") as f:f.write(json.dumps(evaluation.to_dict(),sort_keys=True)+"\n")
    def load_all(self)->list[Evaluation]:
        if not self.history.exists():return []
        rows=[]
        for line in self.history.read_text(encoding="utf-8").splitlines():
            if not line.strip():continue
            data=json.loads(line);cdata=data["candidate"];candidate=Candidate(mechanism=cdata["mechanism"],params=cdata["params"],parents=tuple(cdata.get("parents",[])),generation=int(cdata.get("generation",0)),origin=cdata.get("origin","unknown"));evaluation=Evaluation(candidate=candidate,stages=[StageResult(**s) for s in data.get("stages",[])],deepest_stage=data.get("deepest_stage","none"),feasible=bool(data.get("feasible",False)),objectives={k:float(v) for k,v in data.get("objectives",{}).items()},physical_gate=data.get("physical_gate",{}));rows.append(evaluation)
        return rows
    def write_checkpoint(self,payload:dict[str,Any])->None:self.checkpoint.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    def read_checkpoint(self)->dict[str,Any]:return json.loads(self.checkpoint.read_text(encoding="utf-8")) if self.checkpoint.exists() else {}
    def write_json(self,name:str,payload:Any)->None:(self.root/name).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
