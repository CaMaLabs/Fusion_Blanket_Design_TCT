import json
from pathlib import Path

ROOT = Path(".")
OUT = ROOT / "jorek_handoff"
OUT.mkdir(exist_ok=True)

reference = {
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
    "reduced_model_best_basin": {
        "edge_drive_range": [0.65, 0.80],
        "best_cluster": {
            "edge_drive": [0.65, 0.70],
            "v_tor": [0.65, 0.75],
            "v_pol": [0.20, 0.30],
            "tct_gain": [0.65, 0.75],
        },
        "directional_result": {
            "higher_tct_gain_reduces_severity": True,
            "higher_toroidal_flow_reduces_severity": True,
            "moderate_poloidal_flow_helps_via_shear": True,
            "edge_shear_improves_stability_window": True,
        },
    },
    "jorek_translation": {
        "edge_drive": {
            "maps_to": [
                "pedestal pressure gradient",
                "edge current gradient / peeling-ballooning drive"
            ],
            "notes": "Primary instability drive surrogate from reduced model."
        },
        "v_tor": {
            "maps_to": [
                "toroidal flow / rotation assumption",
                "neoclassical flow-related setup"
            ],
            "notes": "Strong stabilizing trend in reduced model."
        },
        "v_pol": {
            "maps_to": [
                "poloidal flow assumption",
                "shear-supporting flow component"
            ],
            "notes": "Secondary lever, mainly useful through edge shear."
        },
        "edge_shear": {
            "maps_to": [
                "derived edge flow shear",
                "E×B-like shear surrogate"
            ],
            "notes": "Do not treat as direct input; derive from chosen flow scenario."
        },
        "tct_gain": {
            "maps_to": [
                "surrogate stabilization scenario",
                "profile shaping / transport / current-gradient control assumption"
            ],
            "notes": "Not a native JOREK variable. Must be represented indirectly."
        },
    },
    "first_campaign": {
        "goal": "Test whether stronger stabilization and flow reduce ELM / edge-burst severity in the same direction as the reduced model.",
        "cases": [
            {
                "name": "baseline_low_control",
                "description": "Lower-flow, lower-stabilization reference."
            },
            {
                "name": "high_flow_case",
                "description": "Higher toroidal flow and moderate poloidal flow."
            },
            {
                "name": "stabilized_surrogate_case",
                "description": "Profile/control surrogate for stronger TCT-like stabilization."
            },
            {
                "name": "combined_case",
                "description": "High flow plus stabilized surrogate."
            },
        ],
        "outputs_to_compare": [
            "ELM crash amplitude",
            "energy loss per ELM",
            "peak divertor heat flux",
            "wetted area",
            "ELM frequency",
            "stability threshold/window shift",
        ],
    },
}

translation_md = """# JOREK Handoff Notes

## Frozen engineering reference
- radius_cm = 55
- R = 0.55 m
- a = 0.55 m
- li_current = 0.1
- TCT supervisor = aggressive
- severity_scale = 0.6
- blanket = be_outer_kill
- ordering = Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be
- split = (0.15, 0.20, 0.40, 0.15, 0.10)
- blanket_thickness = 1.25
- axial_outer_cap_thickness = 0.6

## Reduced-model result to preserve
The reduced edge model found the best basin near:
- edge_drive ~ 0.65-0.70
- v_tor ~ 0.65-0.75
- v_pol ~ 0.20-0.30
- tct_gain ~ 0.65-0.75

Directional result:
- stronger TCT-like stabilization reduces severity
- higher toroidal flow reduces severity
- moderate poloidal flow helps through shear
- edge shear widens the safe operating window

## Translation into JOREK language
- edge_drive -> pedestal / edge pressure-current drive
- v_tor -> toroidal flow assumption
- v_pol -> poloidal flow assumption
- edge_shear -> derived from the flow scenario
- tct_gain -> indirect stabilization surrogate, not a native JOREK knob

## Minimal first campaign
1. baseline_low_control
2. high_flow_case
3. stabilized_surrogate_case
4. combined_case

## Compare on
- ELM crash amplitude
- energy loss per ELM
- peak divertor heat flux
- wetted area
- ELM frequency
- stability window shift
"""

campaign_yaml = """campaign:
  name: jorek_first_edge_validation
  frozen_reference:
    radius_cm: 55
    R_m: 0.55
    a_m: 0.55
    li_current: 0.10
    blanket_topology: be_outer_kill

  cases:
    - name: baseline_low_control
      edge_drive: nominal
      toroidal_flow: low
      poloidal_flow: low
      stabilization_surrogate: low

    - name: high_flow_case
      edge_drive: nominal
      toroidal_flow: high
      poloidal_flow: moderate
      stabilization_surrogate: low

    - name: stabilized_surrogate_case
      edge_drive: nominal
      toroidal_flow: low
      poloidal_flow: low
      stabilization_surrogate: high

    - name: combined_case
      edge_drive: nominal
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
"""

(OUT / "jorek_handoff_reference.json").write_text(
    json.dumps(reference, indent=2),
    encoding="utf-8",
)
(OUT / "jorek_translation_notes.md").write_text(
    translation_md,
    encoding="utf-8",
)
(OUT / "jorek_first_campaign.yaml").write_text(
    campaign_yaml,
    encoding="utf-8",
)

print("Wrote:")
print(OUT / "jorek_handoff_reference.json")
print(OUT / "jorek_translation_notes.md")
print(OUT / "jorek_first_campaign.yaml")
