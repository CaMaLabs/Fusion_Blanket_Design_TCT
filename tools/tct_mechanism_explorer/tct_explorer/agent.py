from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

from .mechanisms import candidate_from_proposal


class AgentSupervisor:
    def __init__(self, cfg: dict[str, Any], output_dir: Path) -> None:
        self.cfg = cfg
        self.output_dir = output_dir / "agent"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def advise(self, generation: int, summary: dict[str, Any]) -> dict[str, Any]:
        command = str(self.cfg["agent"].get("command", "")).strip()
        if not command:
            return {"mechanism_weights": {}, "proposals": [], "notes": "agent disabled"}

        request_path = self.output_dir / f"generation_{generation:04d}_request.json"
        request_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        p = subprocess.run(
            shlex.split(command),
            input=json.dumps(summary),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(self.cfg["agent"]["timeout_seconds"]),
        )
        response_record = {
            "return_code": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
        (self.output_dir / f"generation_{generation:04d}_raw.json").write_text(
            json.dumps(response_record, indent=2) + "\n", encoding="utf-8"
        )
        if p.returncode:
            return {"mechanism_weights": {}, "proposals": [], "notes": "agent command failed"}
        try:
            payload = json.loads(p.stdout)
            if not isinstance(payload, dict):
                raise ValueError("agent response is not an object")
            payload.setdefault("mechanism_weights", {})
            payload.setdefault("proposals", [])
            return payload
        except Exception as exc:
            return {"mechanism_weights": {}, "proposals": [], "notes": f"invalid agent response: {exc}"}

    @staticmethod
    def validated_proposals(payload: dict[str, Any], generation: int) -> list:
        out = []
        for proposal in payload.get("proposals", []):
            try:
                out.append(candidate_from_proposal(proposal, generation))
            except Exception:
                continue
        return out
