#!/usr/bin/env python3
"""Audit whether the reduced segmented-electrode comparison is truly energy matched.

This is a diagnostic-only audit. It does not modify actuator or solver physics.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation_runs/tct_segmented_electrode_audit/summary.json"
OUTDIR = ROOT / "validation_runs/tct_segmented_electrode_energy_match_audit"
OUT = OUTDIR / "summary.json"
TOL_FRAC = 0.01


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    cases = {c["case"]: c for c in source["cases"]}
    segmented = cases["segmented_static"]
    unsegmented = cases["equivalent_energy_unsegmented"]
    e_seg = float(segmented["actuator_energy_reduced"])
    e_uni = float(unsegmented["actuator_energy_reduced"])
    rel = abs(e_uni - e_seg) / max(abs(e_seg), 1e-30)
    matched = rel <= TOL_FRAC

    result = {
        "classification": (
            "TCT_SEGMENTED_ELECTRODE_ENERGY_MATCH_CONFIRMED"
            if matched else "TCT_SEGMENTED_ELECTRODE_ENERGY_MATCH_NOT_ESTABLISHED"
        ),
        "formal_m3dc1_classification": None,
        "pipeline_failure": False,
        "reduced_model_only": True,
        "source_classification": source.get("classification"),
        "comparison": {
            "segmented_case": segmented["case"],
            "segmented_energy_reduced": e_seg,
            "unsegmented_case": unsegmented["case"],
            "unsegmented_energy_reduced": e_uni,
            "relative_energy_mismatch": rel,
            "tolerance_fraction_le": TOL_FRAC,
            "energy_match_pass": matched,
        },
        "frozen_gates": source.get("frozen_gates"),
        "zero_field_control_present": "no_electrode" in cases,
        "interpretation": (
            "The existing equal-energy control is within tolerance."
            if matched else
            "The case labelled equivalent_energy_unsegmented is not energy matched to segmented_static; efficacy differences must not be attributed to segmentation until a genuinely matched control is generated."
        ),
        "claim_boundary": "Reduced-model energy-accounting audit only. No native M3D-C1 electrode efficacy, experimental, reactor-scale, precursor, or species-separation claim.",
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
