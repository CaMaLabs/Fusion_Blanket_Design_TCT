from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Callable

from .models import Candidate

SAFE_INPUT_KEYS = {"imag_control","mag_ctrl_amp","mag_ctrl_r0","mag_ctrl_z0","mag_ctrl_wr","mag_ctrl_wz","mag_ctrl_t_on","mag_ctrl_t_ramp","mag_ctrl_t_off","icd_source","J_0cd","R_0cd","Z_0cd","W_cd","W_cd_shoulder","delta_cd","cd_t_on","cd_t_ramp","cd_t_off","ntimemax","ntimepr"}
FORBIDDEN_PHYSICS_KEYS = {"eta","nu","eps","gem_sheet_scale","resistivity","viscosity"}

@dataclass(frozen=True)
class Param:
    low: float
    high: float
    kind: str = "float"
    def sample(self, rng: random.Random) -> float | int:
        if self.kind == "int": return rng.randint(int(self.low), int(self.high))
        return rng.uniform(self.low, self.high)
    def clamp(self, value: float | int) -> float | int:
        value = min(max(float(value), self.low), self.high)
        return int(round(value)) if self.kind == "int" else float(value)

@dataclass(frozen=True)
class Mechanism:
    name: str
    params: dict[str, Param]
    adapter: Callable[[dict[str, Any], str, dict[str, Any]], dict[str, Any]]
    description: str
    def normalize(self, params: dict[str, Any]) -> dict[str, Any]:
        unknown = set(params) - set(self.params)
        if unknown: raise ValueError(f"{self.name}: unknown parameters {sorted(unknown)}")
        out = {}
        for name, spec in self.params.items():
            if name not in params: raise ValueError(f"{self.name}: missing parameter {name}")
            value = params[name]
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)): raise ValueError(f"{self.name}.{name} must be finite numeric")
            out[name] = spec.clamp(value)
        return out

def _times(params, stage, cfg):
    t_on = float(params["t_on"]); duration = float(params["duration"])
    if stage == "impulse": duration = float(cfg["stages"]["probe_duration"])
    return t_on, t_on + max(duration, 0.0)

def _magnetic(p, stage, cfg):
    t_on, t_off = _times(p, stage, cfg)
    return {"imag_control":1,"mag_ctrl_amp":p["amp"],"mag_ctrl_r0":p["r0"],"mag_ctrl_z0":p["z0"],"mag_ctrl_wr":p["wr"],"mag_ctrl_wz":p["wz"],"mag_ctrl_t_on":t_on,"mag_ctrl_t_ramp":p["ramp"],"mag_ctrl_t_off":t_off,"icd_source":0,"J_0cd":0.0}

def _current_drive(p, stage, cfg):
    t_on, t_off = _times(p, stage, cfg)
    return {"imag_control":0,"mag_ctrl_amp":0.0,"icd_source":1,"J_0cd":p["amp"],"R_0cd":p["r0"],"Z_0cd":p["z0"],"W_cd":p["width"],"cd_t_on":t_on,"cd_t_ramp":p["ramp"],"cd_t_off":t_off}

def _redistribution(p, stage, cfg):
    t_on, t_off = _times(p, stage, cfg)
    return {"imag_control":0,"mag_ctrl_amp":0.0,"icd_source":4,"J_0cd":p["amp"],"R_0cd":p["r0"],"Z_0cd":p["z0"],"W_cd":p["center_width"],"W_cd_shoulder":p["shoulder_width"],"delta_cd":p["shoulder_delta"],"cd_t_on":t_on,"cd_t_ramp":p["ramp"],"cd_t_off":t_off}

def _hybrid(p, stage, cfg):
    t_on, t_off = _times(p, stage, cfg)
    return {"imag_control":1,"mag_ctrl_amp":p["mag_amp"],"mag_ctrl_r0":p["r0"],"mag_ctrl_z0":p["z0"],"mag_ctrl_wr":p["mag_wr"],"mag_ctrl_wz":p["mag_wz"],"mag_ctrl_t_on":t_on,"mag_ctrl_t_ramp":p["ramp"],"mag_ctrl_t_off":t_off,"icd_source":4,"J_0cd":p["redistribution_amp"],"R_0cd":p["r0"],"Z_0cd":p["z0"],"W_cd":p["center_width"],"W_cd_shoulder":p["shoulder_width"],"delta_cd":p["shoulder_delta"],"cd_t_on":t_on,"cd_t_ramp":p["ramp"],"cd_t_off":t_off}

COMMON_TIME = {"t_on":Param(0.0,0.22),"duration":Param(0.025,0.25),"ramp":Param(0.0,0.05)}
REGISTRY = {
 "magnetic_pulse": Mechanism("magnetic_pulse", {"amp":Param(-0.03,0.03),"r0":Param(9.5,10.5),"z0":Param(0.5,1.5),"wr":Param(0.2,1.0),"wz":Param(0.2,1.0),**COMMON_TIME}, _magnetic, "Localized native magnetic/flux control operator."),
 "current_drive": Mechanism("current_drive", {"amp":Param(-0.25,0.25),"r0":Param(9.5,10.5),"z0":Param(0.5,1.5),"width":Param(0.2,1.0),**COMMON_TIME}, _current_drive, "Localized native current-drive source."),
 "current_redistribution": Mechanism("current_redistribution", {"amp":Param(-0.25,0.25),"r0":Param(9.5,10.5),"z0":Param(0.5,1.5),"center_width":Param(0.15,0.8),"shoulder_width":Param(0.15,0.8),"shoulder_delta":Param(0.2,1.1),**COMMON_TIME}, _redistribution, "Net-current-neutral center/shoulder current redistribution."),
 "hybrid_mag_redistribution": Mechanism("hybrid_mag_redistribution", {"mag_amp":Param(-0.03,0.03),"redistribution_amp":Param(-0.25,0.25),"r0":Param(9.5,10.5),"z0":Param(0.5,1.5),"mag_wr":Param(0.2,1.0),"mag_wz":Param(0.2,1.0),"center_width":Param(0.15,0.8),"shoulder_width":Param(0.15,0.8),"shoulder_delta":Param(0.2,1.1),**COMMON_TIME}, _hybrid, "Combined magnetic shaping plus current redistribution.")}

def validate_updates(updates):
    forbidden = set(updates) & FORBIDDEN_PHYSICS_KEYS
    if forbidden: raise ValueError(f"forbidden physics keys: {sorted(forbidden)}")
    unknown = set(updates) - SAFE_INPUT_KEYS
    if unknown: raise ValueError(f"non-allowlisted C1input keys: {sorted(unknown)}")

def candidate_updates(candidate, stage, cfg):
    mech = REGISTRY[candidate.mechanism]; params = mech.normalize(candidate.params); out = mech.adapter(params, stage, cfg); out["ntimepr"] = int(cfg["stages"]["ntimepr"])
    out["ntimemax"] = int(cfg["stages"]["probe_ntimemax"] if stage=="impulse" else cfg["stages"]["sustained_ntimemax"] if stage=="sustained" else cfg["stages"]["full_ntimemax"])
    validate_updates(out); return out

def random_candidate(mechanism, rng, generation=0):
    mech = REGISTRY[mechanism]; return Candidate(mechanism=mechanism, params={n:s.sample(rng) for n,s in mech.params.items()}, generation=generation, origin="random")

def zero_candidate(mechanism, rng=None):
    rng = rng or random.Random(0); c = random_candidate(mechanism, rng); p = dict(c.params)
    if mechanism == "hybrid_mag_redistribution": p["mag_amp"] = p["redistribution_amp"] = 0.0
    else: p["amp"] = 0.0
    return Candidate(mechanism=mechanism, params=p, generation=-1, origin="zero_equivalence")

def mutate(candidate, rng, scale, generation):
    mech = REGISTRY[candidate.mechanism]; p = dict(candidate.params); keys = list(mech.params); count = max(1,min(len(keys),1+int(rng.random()*3)))
    for key in rng.sample(keys,count):
        s=mech.params[key]; p[key]=s.clamp(float(p[key])+rng.gauss(0.0,(s.high-s.low)*scale))
    return Candidate(candidate.mechanism,p,(candidate.candidate_id,),generation,"mutation")

def crossover(a,b,rng,generation):
    if a.mechanism != b.mechanism: return a
    p={k:(a.params[k] if rng.random()<0.5 else b.params[k]) for k in REGISTRY[a.mechanism].params}
    return Candidate(a.mechanism,p,(a.candidate_id,b.candidate_id),generation,"crossover")

def candidate_from_proposal(proposal, generation):
    mechanism = str(proposal["mechanism"])
    if mechanism not in REGISTRY: raise ValueError(f"unknown proposed mechanism: {mechanism}")
    mech = REGISTRY[mechanism]; supplied = dict(proposal.get("params") or {}); params={}
    for key,spec in mech.params.items():
        value = supplied[key] if key in supplied else 0.5*(spec.low+spec.high); params[key]=spec.clamp(value)
    unknown = set(supplied)-set(mech.params)
    if unknown: raise ValueError(f"agent proposal has unknown parameters: {sorted(unknown)}")
    return Candidate(mechanism,params,generation=generation,origin="agent")
