#!/usr/bin/env python3
"""Audit whether the reduced response model can identify a spatial segmentation benefit.

This is a structural diagnostic only. It does not modify actuator or solver physics.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "tools/tct_mechanism_explorer/run_segmented_electrode_audit.py"
SOURCE = ROOT / "validation_runs/tct_segmented_electrode_energy_matched_advantage_audit/summary.json"
OUTDIR = ROOT / "validation_runs/tct_segmented_electrode_spatial_identifiability_audit"
OUT = OUTDIR / "summary.json"


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    text = MODEL.read_text(encoding="utf-8")

    # Fail closed: the current response closure reduces each field snapshot to one
    # scalar (peak_abs_shear), then maps that scalar through one transport multiplier.
    # Consequently width/Jpk/high-J do not consume shear-layer location, width, sign,
    # or the full E_r(r,z,t) / dvExB_dr(r,z,t) profile.
    peak_scalar_used = "s=snap['peak_abs_shear']" in text
    scalar_transport_used = "shear_transport_multiplier(s,1.0)" in text
    width_from_scalar_gain = "width=0.045*gain" in text
    jpk_from_scalar_gain = "jpk=-0.18*gain" in text
    highj_from_scalar_gain = "highj=-1.5*gain" in text
    er_profile_consumed_by_response = any(
        marker in text for marker in (
            "snap['E_r']", 'snap["E_r"]',
            "snap['dvExB_dr']", 'snap["dvExB_dr"]',
            "snap['v_ExB']", 'snap["v_ExB"]',
        )
    )

    scalarized = all((peak_scalar_used, scalar_transport_used, width_from_scalar_gain, jpk_from_scalar_gain, highj_from_scalar_gain))
    spatial_identifiability = bool(er_profile_consumed_by_response and not scalarized)

    classification = (
        "TCT_SEGMENTED_ELECTRODE_REDUCED_SPATIAL_IDENTIFIABILITY_ESTABLISHED"
        if spatial_identifiability
        else "TCT_SEGMENTED_ELECTRODE_REDUCED_SPATIAL_IDENTIFIABILITY_NOT_ESTABLISHED"
    )
    result = {
        "classification": classification,
        "formal_m3dc1_classification": None,
        "pipeline_failure": False,
        "reduced_model_only": True,
        "source_classification": source.get("classification"),
        "source_energy_match_pass": source.get("energy_match_pass"),
        "source_segmentation_advantage_pass": source.get("segmentation_advantage_pass"),
        "frozen_gates": source.get("frozen_gates"),
        "zero_field_control_present": source.get("zero_field_control_present"),
        "structural_checks": {
            "peak_abs_shear_scalar_used": peak_scalar_used,
            "scalar_transport_multiplier_used": scalar_transport_used,
            "width_response_from_scalar_gain": width_from_scalar_gain,
            "Jpk_response_from_scalar_gain": jpk_from_scalar_gain,
            "integrated_high_J_response_from_scalar_gain": highj_from_scalar_gain,
            "full_spatial_field_consumed_by_response_metrics": er_profile_consumed_by_response,
        },
        "spatial_segmentation_identifiable_in_current_response_closure": spatial_identifiability,
        "interpretation": (
            "The reduced response closure consumes spatial field structure, so a spatial segmentation comparison is structurally identifiable at this rung."
            if spatial_identifiability
            else "The current reduced response closure scalarizes each snapshot to peak |shear| before computing transport and response metrics. The 074 negative therefore does not test whether shear-layer location/width/sign or moving E_r(r,z,t) structure can help; it only shows no advantage under this scalar closure. Do not promote or reject spatial segmentation from this rung."
        ),
        "next_rung": "Before another segmentation-advantage search, use a spatially resolved plasma-response model (preferably BOUT++ electrostatic potential/vorticity coupling) or an independently justified spatial reduced closure with zero-equivalence and energy-matched controls.",
        "claim_boundary": "Reduced-model structural identifiability audit only. No native M3D-C1 electrode efficacy, experimental, reactor-scale, precursor, species-separation, or spatial-segmentation efficacy claim.",
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
