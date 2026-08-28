from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Candidate:
    mechanism: str
    params: dict[str, float | int | str | bool]
    parents: tuple[str, ...] = ()
    generation: int = 0
    origin: str = "random"

    @property
    def candidate_id(self) -> str:
        payload = {"mechanism": self.mechanism, "params": self.params}
        return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["candidate_id"] = self.candidate_id
        row["parents"] = list(self.parents)
        return row


@dataclass
class StageResult:
    stage: str
    status: str
    return_code: int | None = None
    metrics: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    gates: dict[str, bool | str | float | None] = field(default_factory=dict)
    run_dir: str | None = None
    input_sha256: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evaluation:
    candidate: Candidate
    stages: list[StageResult] = field(default_factory=list)
    deepest_stage: str = "none"
    feasible: bool = False
    objectives: dict[str, float] = field(default_factory=dict)
    physical_gate: dict[str, Any] = field(default_factory=dict)

    def stage(self, name: str) -> StageResult | None:
        for item in self.stages:
            if item.stage == name:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"candidate": self.candidate.to_dict(), "stages": [s.to_dict() for s in self.stages], "deepest_stage": self.deepest_stage, "feasible": self.feasible, "objectives": self.objectives, "physical_gate": self.physical_gate}
