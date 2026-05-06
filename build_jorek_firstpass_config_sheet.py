import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

config = {
    "package_name": "jorek_firstpass_config",
    "status": "draft_needs_confirmation",
    "purpose": (
        "First-pass physics and numerics decision sheet for the initial "
        "4-case JOREK campaign built around the frozen 55 cm reference."
    ),
    "frozen_reference": {
        "reference_name": "55cm_be_outer_kill_mainline",
        "radius_cm": 55.0,
        "R_m": 0.55,
        "a_m": 0.55,
        "li_current": 0.10,
        "tct_supervisor": "aggressive",
        "severity_scale": 0.6,
        "blanket_topology": "be_outer_kill",
        "blanket_ordering": [
            "Be",
            "Li2O",
            "Li2O",
            "W_Ti_B4C_60_30_10_wt",
            "Be",
        ],
        "blanket_split": [0.15, 0.20, 0.40, 0.15, 0.10],
        "blanket_thickness": 1.25,
        "axial_outer_cap_thickness": 0.6,
    },
    "recommended_firstpass_physics": {
        "reduced_mhd": {
            "value": True,
            "why": "Cleanest serious first launch path for edge/ELM behavior before adding full complexity."
        },
        "two_fluid": {
            "value": False,
            "why": "Add later if the first-pass campaign shows promising directional agreement."
        },
        "diamagnetic_effects": {
            "value": True,
            "why": "Flow/rotation-sensitive edge dynamics likely matter for your hypothesis."
        },
        "neoclassical_flow": {
            "value": True,
            "why": "Useful because the reduced-model best basin depends strongly on flow/shear."
        },
        "resistive_wall": {
            "value": False,
            "why": "Not the first lever to test; enable later once baseline edge behavior is stable."
        },
        "sheath_boundary_conditions": {
            "value": True,
            "why": "You care about divertor heat load and edge-event severity, so boundary realism matters."
        },
        "sol_divertor_treatment": {
            "value": "enabled_if_practical",
            "why": "Desired for heat-flux comparison, but can be simplified if setup burden is too high on pass 1."
        },
        "impurity_or_radiation_model": {
            "value": False,
            "why": "Not needed for the first directional validation pass."
        },
    },
    "recommended_firstpass_numerics": {
        "mesh_plan": {
            "value": "moderate_startup_mesh",
            "why": "Do not start with production resolution; prove the case structure first."
        },
        "toroidal_harmonics": {
            "value": "moderate",
            "why": "Enough to resolve edge activity trends without overcommitting compute on pass 1."
        },
        "time_step_strategy": {
            "value": "conservative_adaptive_if_available",
            "why": "Edge bursts can be stiff; avoid aggressive stepping on initial runs."
        },
        "total_runtime_strategy": {
            "value": "long_enough_to_capture_recurrent_event_behavior",
            "why": "Need more than one burst or quasi-cycle to compare cases meaningfully."
        },
        "output_cadence": {
            "value": "high_around_events",
            "why": "Must resolve crash amplitude and peak divertor heat-flux behavior."
        },
        "restart_strategy": {
            "value": "checkpoint_enabled",
            "why": "You do not want to lose expensive partially completed runs."
        },
    },
    "case_intent": {
        "case_A_baseline_low_control": {
            "flow_state": "low",
            "stabilization_surrogate": "low",
            "expected_role": "baseline reference",
        },
        "case_B_high_flow": {
            "flow_state": "high_tor_moderate_pol",
            "stabilization_surrogate": "low",
            "expected_role": "tests pure flow/shear benefit",
        },
        "case_C_stabilized_surrogate": {
            "flow_state": "low",
            "stabilization_surrogate": "high",
            "expected_role": "tests pure stabilization-surrogate benefit",
        },
        "case_D_combined": {
            "flow_state": "high_tor_moderate_pol",
            "stabilization_surrogate": "high",
            "expected_role": "best expected case if concept survives translation",
        },
    },
    "required_outputs": [
        "elm_crash_amplitude",
        "elm_energy_loss_per_event",
        "peak_divertor_heat_flux",
        "wetted_area",
        "elm_frequency",
        "stability_window_shift",
    ],
    "launch_blockers_remaining": [
        "real_or_explicitly_accepted_synthetic_equilibrium_choice",
        "profile_definitions_accepted_for_all_4_cases",
        "explicit_boundary_and_divertor_treatment_choice",
        "explicit_mesh_and_timestep_choice",
        "postprocessing_method_for_required_outputs",
    ],
}

readme = """# JOREK First-Pass Physics/Numerics Config

## Purpose
This file records the first-pass recommended physics switches and numerical strategy
for the initial 4-case JOREK campaign.

## Recommended philosophy
Do not try to launch the most complete and expensive model first.
Launch the cleanest serious case that can still test your claim:

- flow matters
- shear matters
- stabilization surrogate matters
- combined case should reduce edge-event severity

## First-pass recommendation
- reduced MHD: yes
- two-fluid: no on pass 1
- diamagnetic effects: yes
- neoclassical flow: yes
- resistive wall: no on pass 1
- sheath BC: yes
- SOL/divertor treatment: enable if practical
- impurity/radiation: no on pass 1

## Why
The first campaign should answer:
Does the combined high-flow + stabilization-surrogate case beat the baseline on:
- ELM crash amplitude
- peak divertor heat flux
- stability window shift

## Important
This is a decision sheet, not a runnable JOREK input deck.
It tells you what must be chosen next.
"""

template_md = """# JOREK First-Pass Config Fill Sheet

Fill in the concrete choices for the first campaign.

## Physics switches
- reduced MHD:
- two-fluid:
- diamagnetic effects:
- neoclassical flow:
- resistive wall:
- sheath BC:
- SOL/divertor treatment:
- impurity/radiation:

## Numerics
- mesh plan:
- toroidal harmonics:
- timestep strategy:
- total runtime:
- output cadence:
- checkpoint/restart:

## Per-case interpretation

### Case A
- baseline role:
- exact flow interpretation:
- exact stabilization-surrogate interpretation:

### Case B
- exact high-flow interpretation:
- exact toroidal flow choice:
- exact poloidal flow choice:

### Case C
- exact stabilization-surrogate interpretation:

### Case D
- exact combined interpretation:

## Postprocessing
- elm_crash_amplitude extraction:
- elm_energy_loss_per_event extraction:
- peak_divertor_heat_flux extraction:
- wetted_area extraction:
- elm_frequency extraction:
- stability_window_shift extraction:

## Go / no-go
- Are blockers removed?
- Is the synthetic seed still being used?
- If yes, is that acceptable for a first synthetic campaign?
"""

(OUT / "jorek_firstpass_config.json").write_text(
    json.dumps(config, indent=2),
    encoding="utf-8",
)
(OUT / "jorek_firstpass_config_README.md").write_text(
    readme,
    encoding="utf-8",
)
(OUT / "jorek_firstpass_config_fill_sheet.md").write_text(
    template_md,
    encoding="utf-8",
)

print("Wrote:")
print(" -", OUT / "jorek_firstpass_config.json")
print(" -", OUT / "jorek_firstpass_config_README.md")
print(" -", OUT / "jorek_firstpass_config_fill_sheet.md")
