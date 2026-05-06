import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

reconstruction = {
    "purpose": (
        "Published-case reconstruction pack for choosing a real JOREK anchor scenario "
        "for the first edge/ELM campaign."
    ),
    "status": "literature_anchored_reconstruction",
    "recommended_anchor_case": {
        "name": "published_multi_ELM_cycle_Xpoint_baseline",
        "why": (
            "Best first anchor because it is explicitly a realistic X-point JOREK ELM-cycle case "
            "with divertor power-deposition relevance and diamagnetic-rotation sensitivity."
        ),
        "source_label": "PRL_2015_multi_ELM_cycle",
    },
    "published_case_anchors": [
        {
            "source_label": "PRL_2015_multi_ELM_cycle",
            "title": "Resistive reduced MHD modeling of multi-edge-localized-mode cycles in tokamak X-point plasmas",
            "year": 2015,
            "geometry_type": "realistic tokamak X-point geometry",
            "plasma_regime": "multi-ELM cycle / type-I-ELM-like edge relaxation scenario",
            "physics_scope": {
                "reduced_mhd": True,
                "diamagnetic_rotation": True,
                "divertor_power_deposition": True,
                "sol_divertor_context": "present via target power deposition discussion",
            },
            "key_takeaways": [
                "Good anchor for baseline ELM-cycle reconstruction.",
                "Diamagnetic rotation is a key stabilizing ingredient after crashes.",
                "Power deposition on inner and outer divertor targets is a core comparison output.",
            ],
            "maps_to_project": {
                "case_A_baseline_low_control": "best published anchor for baseline",
                "case_B_high_flow": "flow-sensitive comparison against baseline",
                "case_C_stabilized_surrogate": "profile/control comparison against baseline",
                "case_D_combined": "combined comparison against same baseline",
            },
        },
        {
            "source_label": "RMP_multi_ELM_mitigation_case",
            "title": "Non-linear MHD modeling of edge localized mode cycles and mitigation by resonant magnetic perturbations",
            "year": 2015,
            "geometry_type": "realistic tokamak X-point geometry",
            "plasma_regime": "ELM cycle plus mitigation scenario",
            "physics_scope": {
                "reduced_mhd": True,
                "diamagnetic_rotation": True,
                "rmp_mitigation": True,
                "divertor_target_power_deposition": True,
            },
            "key_takeaways": [
                "Useful second anchor if you later want an explicit mitigation/control story.",
                "Supports the idea that flow/rotation-sensitive stabilization belongs in the comparison set.",
            ],
            "maps_to_project": {
                "case_C_stabilized_surrogate": "closest conceptual match to added stabilization",
                "case_D_combined": "later extension candidate once baseline is stable",
            },
        },
        {
            "source_label": "JET_ILW_JPN83334_wall_aligned_grid_case",
            "title": "Wall-aligned grid generator demonstration for large type-I ELM crash handling",
            "year": 2019,
            "geometry_type": "JET-ILW diverted tokamak configuration",
            "plasma_regime": "type-I ELMy H-mode experiment",
            "experiment_reference": {
                "device": "JET-ILW",
                "pulse": "JPN-83334",
                "Bt_T": 2.4,
                "Ip_MA": 2.4,
            },
            "physics_scope": {
                "wall_aligned_grid": True,
                "sheath_boundary_conditions": True,
                "first_wall_heat_flux": True,
                "divertor_heat_flux": True,
            },
            "key_takeaways": [
                "Best anchor for heat-flux extraction realism.",
                "Strong candidate later when translating baseline case toward more concrete divertor/target handling.",
            ],
            "maps_to_project": {
                "heat_flux_extraction": "strong anchor for peak divertor heat-flux and wetted-area conventions",
            },
        },
    ],
    "first_pass_case_A_recommendation": {
        "anchor_choice": "PRL_2015_multi_ELM_cycle",
        "case_identity": {
            "case_name": "case_A_baseline_low_control",
            "device_style": "generic diverted tokamak / JET-like X-point baseline",
            "geometry_type": "lower single null X-point",
            "regime": "type-I-ELM-like edge cycle baseline",
        },
        "recommended_physics": {
            "reduced_mhd": True,
            "diamagnetic_effects": True,
            "neoclassical_flow": True,
            "two_fluid": False,
            "resistive_wall": False,
            "sheath_boundary_conditions": True,
            "sol_divertor_treatment": "enabled_if_practical",
        },
        "recommended_outputs": [
            "ELM crash amplitude",
            "ELM energy loss per event",
            "peak divertor heat flux",
            "wetted area",
            "ELM frequency",
            "stability window shift",
        ],
        "recommended_interpretation": [
            "Case A should be the boring baseline.",
            "Do not make Case A clever; keep it as the reference edge/ELM case.",
            "Use the same extraction conventions later for B/C/D.",
        ],
    },
    "what_is_still_missing": [
        "actual JOREK input deck syntax from a real example/input file",
        "actual equilibrium include or file path",
        "actual profile include syntax",
        "actual diagnostic variable names",
    ],
}

notes_md = """# JOREK Published-Case Reconstruction

## Purpose
Anchor the first JOREK campaign to published cases instead of leaving it purely synthetic.

## Recommended anchor
Use the 2015 multi-ELM-cycle in realistic X-point geometry case as the first baseline anchor.

Why:
- realistic tokamak X-point geometry
- nonlinear reduced MHD
- explicit multi-ELM cycle
- diamagnetic rotation matters
- divertor target power deposition is a core output

## Second anchor
Use the RMP mitigation paper as the conceptual control/stabilization extension.

## Heat-flux anchor
Use the JET-ILW JPN-83334 wall-aligned-grid / large type-I ELM case as the heat-flux realism anchor.

## First-pass Case A interpretation
- generic diverted X-point baseline
- reduced MHD
- diamagnetic effects on
- neoclassical flow on
- sheath BC on
- SOL/divertor enabled if practical
- low-control / low-flow reference

## Important
This still does NOT give you a real downloadable JOREK input file.
It gives you a literature-grounded baseline identity so your campaign is no longer floating.
"""

case_a_patch_md = """# Case A Replacement Map from Published Reconstruction

Apply these substitutions to:
- runs/case_A_baseline_low_control/case_template.json
- runs/case_A_baseline_low_control/case_template.md

## Replace conceptual identity with:
- device_style = generic diverted tokamak / JET-like baseline
- geometry_type = lower single null X-point
- regime = type-I-ELM-like edge-cycle baseline
- published_anchor = PRL_2015_multi_ELM_cycle

## Replace physics stance with:
- reduced_mhd = true
- diamagnetic_effects = true
- neoclassical_flow = true
- two_fluid = false
- resistive_wall = false
- sheath_boundary_conditions = true
- sol_divertor_treatment = enabled_if_practical

## Keep Case A boring
- low toroidal flow baseline
- low poloidal flow baseline
- low stabilization surrogate
- nominal-high edge drive baseline

## Do not claim yet
- real equilibrium file
- real JOREK syntax
- real diagnostic variable names
"""

(OUT / "jorek_published_case_reconstruction.json").write_text(
    json.dumps(reconstruction, indent=2),
    encoding="utf-8",
)
(OUT / "jorek_published_case_reconstruction.md").write_text(
    notes_md,
    encoding="utf-8",
)
(OUT / "jorek_case_A_published_replacement_map.md").write_text(
    case_a_patch_md,
    encoding="utf-8",
)

print("Wrote:")
print(" -", OUT / "jorek_published_case_reconstruction.json")
print(" -", OUT / "jorek_published_case_reconstruction.md")
print(" -", OUT / "jorek_case_A_published_replacement_map.md")
