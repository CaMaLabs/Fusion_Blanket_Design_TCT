#!/usr/bin/env python3
"""Generate a genuinely energy-matched unsegmented reduced-model control.

Diagnostic/falsification rung only. This does not modify actuator or solver physics.
It rescales the existing unsegmented command and reruns the same reduced simulator
until integrated actuator energy matches segmented_static within 1%.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation_runs/tct_segmented_electrode_audit/summary.json"
OUTDIR = ROOT / "validation_runs/tct_segmented_electrode_energy_matched_control_audit"
OUT = OUTDIR / "summary.json"
TOL = 0.01


def load_audit_module():
    path = ROOT / "tools/tct_mechanism_explorer/run_segmented_electrode_audit.py"
    spec = importlib.util.spec_from_file_location("tct_segmented_audit", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    cases = {c["case"]: c for c in source["cases"]}
    target = float(cases["segmented_static"]["actuator_energy_reduced"])
    mod = load_audit_module()

    def run(scale: float):
        zones = mod.make_zones(1, "uniform")
        base = zones[0].command
        zones[0].command = lambda t, base=base, scale=scale: scale * base(t)
        zones[0].v_limit = max(zones[0].v_limit, 8.0)
        zones[0].i_limit = max(zones[0].i_limit, 8.0)
        zones[0].slew_v_per_t = max(zones[0].slew_v_per_t, 64.0)
        return mod.simulate("energy_matched_unsegmented", zones)

    lo, hi = 0.0, 8.0
    best = None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        case = run(mid)
        e = float(case["actuator_energy_reduced"])
        rel = abs(e - target) / max(abs(target), 1e-30)
        if best is None or rel < best[0]:
            best = (rel, mid, case)
        if e < target:
            lo = mid
        else:
            hi = mid
    rel, scale, matched_case = best
    passed = rel <= TOL

    result = {
        "classification": "TCT_SEGMENTED_ELECTRODE_ENERGY_MATCHED_CONTROL_ESTABLISHED" if passed else "TCT_SEGMENTED_ELECTRODE_ENERGY_MATCHED_CONTROL_NOT_ESTABLISHED",
        "formal_m3dc1_classification": None,
        "pipeline_failure": False,
        "reduced_model_only": True,
        "source_classification": source.get("classification"),
        "target_segmented_energy_reduced": target,
        "matched_unsegmented_energy_reduced": matched_case["actuator_energy_reduced"],
        "relative_energy_mismatch": rel,
        "tolerance_fraction_le": TOL,
        "energy_match_pass": passed,
        "unsegmented_command_scale": scale,
        "matched_control_metrics": {k: v for k, v in matched_case.items() if k != "trace"},
        "segmented_static_metrics": cases["segmented_static"],
        "zero_field_control_present": "no_electrode" in cases,
        "frozen_gates": source.get("frozen_gates"),
        "interpretation": "Energy matching alone permits a segmentation-vs-unsegmented comparison at this reduced-model rung; it does not establish native M3D-C1 electrode efficacy." if passed else "A genuinely energy-matched unsegmented control was not obtained; segmentation efficacy remains uninterpretable.",
        "claim_boundary": "Reduced-model energy-matched-control audit only. No native M3D-C1 electrode efficacy, experimental, reactor-scale, precursor, or species-separation claim."
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
