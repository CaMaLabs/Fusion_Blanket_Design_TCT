#!/usr/bin/env python3
"""Fail-closed comparison of segmented vs genuinely energy-matched unsegmented control.

Reduced-model diagnostic only. No actuator or solver physics is modified.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation_runs/tct_segmented_electrode_energy_matched_control_audit/summary.json"
OUTDIR = ROOT / "validation_runs/tct_segmented_electrode_energy_matched_advantage_audit"
OUT = OUTDIR / "summary.json"
ENERGY_TOL = 0.01


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    seg = source["segmented_static_metrics"]
    unseg = source["matched_control_metrics"]
    energy_match = bool(source.get("energy_match_pass")) and float(source["relative_energy_mismatch"]) <= ENERGY_TOL
    zero_control = bool(source.get("zero_field_control_present"))

    # Positive deltas mean segmentation is better for the corresponding metric.
    width_adv = float(seg["width_gain_pct"]) - float(unseg["width_gain_pct"])
    jpk_adv = float(unseg["Jpk_change_pct"]) - float(seg["Jpk_change_pct"])
    high_j_adv = float(unseg["integrated_high_J_change_pct"]) - float(seg["integrated_high_J_change_pct"])
    sustained_adv = float(seg["sustained_control_fraction"]) - float(unseg["sustained_control_fraction"])

    # Require the established controls/gates and a strict Pareto-style benefit:
    # no degradation in any principal response metric and improvement in at least one.
    metrics = [width_adv, jpk_adv, high_j_adv, sustained_adv]
    eps = 1e-12
    no_degradation = all(x >= -eps for x in metrics)
    any_improvement = any(x > eps for x in metrics)
    frozen_gates_pass = bool(seg.get("width_gate_pass")) and bool(seg.get("Jpk_gate_pass")) and bool(unseg.get("width_gate_pass")) and bool(unseg.get("Jpk_gate_pass"))
    benefit = energy_match and zero_control and frozen_gates_pass and no_degradation and any_improvement

    classification = (
        "TCT_SEGMENTED_ELECTRODE_REDUCED_ENERGY_MATCHED_ADVANTAGE_FOUND"
        if benefit
        else "TCT_SEGMENTED_ELECTRODE_REDUCED_ENERGY_MATCHED_ADVANTAGE_NOT_FOUND"
    )
    result = {
        "classification": classification,
        "formal_m3dc1_classification": None,
        "pipeline_failure": False,
        "reduced_model_only": True,
        "source_classification": source.get("classification"),
        "energy_match_pass": energy_match,
        "relative_energy_mismatch": source.get("relative_energy_mismatch"),
        "energy_tolerance_fraction_le": ENERGY_TOL,
        "zero_field_control_present": zero_control,
        "frozen_gates": source.get("frozen_gates"),
        "frozen_gates_pass_both_cases": frozen_gates_pass,
        "segmented_static_metrics": seg,
        "energy_matched_unsegmented_metrics": unseg,
        "segmentation_advantage_deltas": {
            "width_gain_pct": width_adv,
            "Jpk_change_pct": jpk_adv,
            "integrated_high_J_change_pct": high_j_adv,
            "sustained_control_fraction": sustained_adv,
        },
        "no_principal_metric_degradation": no_degradation,
        "any_principal_metric_improvement": any_improvement,
        "segmentation_advantage_pass": benefit,
        "interpretation": (
            "A reduced-model energy-matched segmentation advantage passed the fail-closed Pareto comparison; this does not establish native M3D-C1 efficacy."
            if benefit
            else "No reduced-model energy-matched segmentation advantage passed the fail-closed Pareto comparison. Do not attribute benefit to segmentation from this rung."
        ),
        "claim_boundary": "Reduced-model energy-matched segmentation comparison only. No native M3D-C1 electrode efficacy, experimental, reactor-scale, precursor, or species-separation claim.",
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
