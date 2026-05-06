import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

reference = {
    "reference_name": "55cm_be_outer_kill_mainline",
    "engineering_reference": {
        "radius_cm": 55.0,
        "R_m": 0.55,
        "a_m": 0.55,
        "li_current": 0.10,
        "tct_supervisor": {
            "enabled": True,
            "level": "aggressive",
            "severity_scale": 0.6,
        },
        "blanket": {
            "topology": "be_outer_kill",
            "ordering": [
                "Be",
                "Li2O",
                "Li2O",
                "W_Ti_B4C_60_30_10_wt",
                "Be",
            ],
            "split": [0.15, 0.20, 0.40, 0.15, 0.10],
            "blanket_thickness": 1.25,
            "axial_outer_cap_thickness": 0.6,
            "lithium_thickness": 0.003,
        },
    },
    "reduced_model_findings": {
        "best_basin": {
            "edge_drive": [0.65, 0.70],
            "v_tor": [0.65, 0.75],
            "v_pol": [0.20, 0.30],
            "tct_gain": [0.65, 0.75],
        },
        "directional_result": {
            "higher_tct_like_stabilization_reduces_severity": True,
            "higher_toroidal_flow_reduces_severity": True,
            "moderate_poloidal_flow_helps_through_shear": True,
            "edge_shear_widens_stability_window": True,
        },
    },
}

translation = {
    "mapping": {
        "edge_drive": {
            "jorek_proxy": [
                "pedestal pressure gradient",
                "edge current gradient / peeling-ballooning drive"
            ],
            "notes": "Use as the primary instability drive scan."
        },
        "v_tor": {
            "jorek_proxy": [
                "toroidal rotation profile",
                "flow / diamagnetic rotation related setup"
            ],
            "notes": "High-value stabilizing lever from reduced model."
        },
        "v_pol": {
            "jorek_proxy": [
                "poloidal flow assumption",
                "flow-shear-supporting component"
            ],
            "notes": "Secondary lever; mainly matters through shear/divertor asymmetry."
        },
        "edge_shear": {
            "jorek_proxy": [
                "derived from toroidal and poloidal flow choices",
                "E×B-shear-like stabilizing regime"
            ],
            "notes": "Not a direct knob; derive from chosen flow scenario."
        },
        "tct_gain": {
            "jorek_proxy": [
                "stabilization surrogate via profile shaping",
                "transport/current-gradient control assumption"
            ],
            "notes": "TCT is not a native JOREK variable. Represent its effect class, not its name."
        },
    }
}

campaign = {
    "campaign_name": "jorek_first_edge_validation",
    "purpose": "Directional validation of the TCT+flow+shear stabilization story in a mainstream edge code path.",
    "cases": [
        {
            "name": "case_A_baseline_low_control",
            "description": "Lower-flow baseline with low stabilization surrogate.",
            "edge_drive": "nominal-high",
            "toroidal_flow": "low",
            "poloidal_flow": "low",
            "stabilization_surrogate": "low",
        },
        {
            "name": "case_B_high_flow",
            "description": "Higher toroidal flow plus moderate poloidal flow.",
            "edge_drive": "same_as_A",
            "toroidal_flow": "high",
            "poloidal_flow": "moderate",
            "stabilization_surrogate": "low",
        },
        {
            "name": "case_C_stabilized_surrogate",
            "description": "Baseline flow with stronger stabilization surrogate.",
            "edge_drive": "same_as_A",
            "toroidal_flow": "low",
            "poloidal_flow": "low",
            "stabilization_surrogate": "high",
        },
        {
            "name": "case_D_combined",
            "description": "High flow plus strong stabilization surrogate.",
            "edge_drive": "same_as_A",
            "toroidal_flow": "high",
            "poloidal_flow": "moderate",
            "stabilization_surrogate": "high",
        },
    ],
    "compare_outputs": [
        "ELM crash amplitude",
        "ELM energy loss per event",
        "peak divertor heat flux",
        "wetted area",
        "ELM frequency",
        "stability threshold / stability window shift",
    ],
    "success_criteria": [
        "Case D better than Case A on crash amplitude and peak divertor heat flux",
        "Case B and/or C improve at least one severity metric vs Case A",
        "Combined case widens safe operating window relative to baseline",
    ],
}

jorek_inputs_needed = {
    "minimum_inputs_checklist": [
        "equilibrium source / EFIT-like or synthetic equilibrium description",
        "pedestal / edge profile assumptions",
        "current profile assumptions",
        "density profile assumptions",
        "temperature profile assumptions",
        "toroidal flow assumption",
        "poloidal flow assumption or equivalent drift-related setup",
        "resistive wall / boundary assumptions",
        "divertor / SOL treatment choice",
        "output extraction plan for ELM and heat-load metrics",
    ],
    "notes": [
        "Do not try to model the entire reactor on pass 1.",
        "Start with a small edge/ELM campaign and compare directional behavior only.",
        "Treat TCT as a stabilization surrogate, not as a claimed native JOREK control field.",
    ],
}

readme = """# JOREK Campaign Package

## Goal
Directional validation of the TCT + flow + shear severity-reduction story in a mainstream edge-code path.

## Frozen engineering reference
- radius_cm = 55
- li_current = 0.1
- TCT supervisor = aggressive
- severity_scale = 0.6
- blanket = be_outer_kill
- ordering = Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be
- split = (0.15, 0.20, 0.40, 0.15, 0.10)
- blanket_thickness = 1.25
- axial_outer_cap_thickness = 0.6

## Reduced-model finding to carry forward
Best basin clustered around:
- edge_drive ~ 0.65-0.70
- v_tor ~ 0.65-0.75
- v_pol ~ 0.20-0.30
- tct_gain ~ 0.65-0.75

Directional result:
- stronger TCT-like stabilization reduces event severity
- stronger toroidal flow reduces event severity
- moderate poloidal flow helps through shear
- edge shear widens the stability window

## Immediate JOREK task
Set up 4 cases:
- baseline_low_control
- high_flow
- stabilized_surrogate
- combined

## Outputs to compare
- ELM crash amplitude
- ELM energy loss per event
- peak divertor heat flux
- wetted area
- ELM frequency
- stability window shift
"""

yaml_text = """campaign:
  name: jorek_first_edge_validation

  frozen_reference:
    radius_cm: 55
    li_current: 0.10
    blanket_topology: be_outer_kill

  cases:
    - name: case_A_baseline_low_control
      edge_drive: nominal_high
      toroidal_flow: low
      poloidal_flow: low
      stabilization_surrogate: low

    - name: case_B_high_flow
      edge_drive: same_as_A
      toroidal_flow: high
      poloidal_flow: moderate
      stabilization_surrogate: low

    - name: case_C_stabilized_surrogate
      edge_drive: same_as_A
      toroidal_flow: low
      poloidal_flow: low
      stabilization_surrogate: high

    - name: case_D_combined
      edge_drive: same_as_A
      toroidal_flow: high
      poloidal_flow: moderate
      stabilization_surrogate: high

  outputs:
    - elm_crash_amplitude
    - elm_energy_loss
    - peak_divertor_heat_flux
    - wetted_area
    - elm_frequency
    - stability_window_shift

  success_criteria:
    - combined_beats_baseline_on_amplitude
    - combined_beats_baseline_on_peak_divertor_heat_flux
    - combined_beats_baseline_on_stability_window
"""

files = {
    "jorek_reference.json": reference,
    "jorek_translation.json": translation,
    "jorek_first_campaign.json": campaign,
    "jorek_inputs_needed.json": jorek_inputs_needed,
}

for name, obj in files.items():
    (OUT / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")

(OUT / "README.md").write_text(readme, encoding="utf-8")
(OUT / "jorek_first_campaign.yaml").write_text(yaml_text, encoding="utf-8")

print("Wrote JOREK campaign package to:")
for p in sorted(OUT.iterdir()):
    print(" -", p)
