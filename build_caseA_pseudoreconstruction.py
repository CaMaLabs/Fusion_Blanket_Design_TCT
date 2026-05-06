import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"
RUN = PKG / "runs" / "case_A_baseline_low_control"

RUN.mkdir(parents=True, exist_ok=True)

json_out = RUN / "case_A_pseudoreconstruction.json"
md_out = RUN / "case_A_pseudoreconstruction.md"

pseudo = {
    "case_name": "case_A_baseline_low_control",
    "purpose": (
        "Paper-faithful pseudo-reconstruction of a JOREK realistic X-point "
        "multi-ELM-cycle baseline for first-pass case construction."
    ),
    "published_anchor": {
        "primary": "PRL_2015_multi_ELM_cycle",
        "secondary": "RMP_multi_ELM_mitigation_case",
        "heat_flux_anchor": "JET_ILW_JPN83334_wall_aligned_grid_case",
    },
    "identity": {
        "device_style": "generic_diverted_tokamak_or_JET_like_baseline",
        "geometry_type": "lower_single_null_X_point",
        "regime": "type_I_ELM_like_edge_cycle_baseline",
        "model_scope": "nonlinear_reduced_MHD_first_pass",
    },
    "geometry_assumptions": {
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
        "q95_target": 3.5,
        "notes": [
            "These are synthetic-but-structured starter assumptions.",
            "Keep geometry explicitly diverted and X-point based.",
            "Replace with real equilibrium input when available."
        ],
    },
    "profile_assumptions": {
        "density": {
            "shape": "core_flat_pedestal_drop",
            "core_n20": 1.0,
            "pedestal_n20": 0.75,
            "edge_n20": 0.30,
        },
        "temperature": {
            "shape": "hot_core_steep_pedestal_cool_edge",
            "core_keV": 12.0,
            "pedestal_keV": 2.2,
            "edge_keV": 0.20,
            "Ti_equals_Te_first_pass": True,
        },
        "pressure": {
            "intent": "baseline_high_drive_edge_cycle_reference",
            "pedestal_pressure_gradient_setting": "baseline_high_drive",
        },
        "current": {
            "shape": "monotonic_core_current_with_edge_current_shoulder",
            "bootstrap_fraction_guess": 0.30,
            "edge_current_gradient_setting": "baseline_high_drive",
        },
    },
    "flow_and_control_assumptions": {
        "toroidal_flow_profile": "low_flow_baseline_profile",
        "poloidal_flow_profile": "low_flow_baseline_profile",
        "edge_shear_definition": "derived_low_shear_from_low_tor_and_low_pol_flow",
        "tct_surrogate_definition": (
            "low surrogate: baseline profile/current-gradient/transport assumptions"
        ),
        "interpretation": [
            "Case A is intentionally the boring baseline.",
            "No added stabilization boost.",
            "No high-flow enhancement.",
            "This is the reference that B/C/D should be compared against."
        ],
    },
    "physics_switches": {
        "reduced_mhd": True,
        "two_fluid": False,
        "diamagnetic_effects": True,
        "neoclassical_flow": True,
        "resistive_wall": False,
        "sheath_boundary_conditions": True,
        "sol_divertor_treatment": "enabled_if_practical",
    },
    "numerics": {
        "mesh_plan": "startup_mesh_v1",
        "mesh_refinement_priority": "pedestal_edge_and_divertor_region",
        "toroidal_harmonics": 8,
        "time_step_value": 1.0e-7,
        "time_step_units": "s",
        "total_runtime_value": 5.0e-3,
        "total_runtime_units": "s",
        "output_cadence_value": 50,
        "output_cadence_units": "steps",
        "checkpoint_cadence_value": 500,
        "checkpoint_cadence_units": "steps",
    },
    "boundary_and_divertor": {
        "boundary_strategy": "first_pass_edge_focused_boundary_set",
        "divertor_representation": "required_for_heat_flux_comparison",
        "sol_model": "enabled_if_practical",
        "sheath_bc": True,
        "target_surface": "divertor_target_primary",
        "peak_heat_flux_statistic": "max_over_target_and_time",
        "wetted_area_threshold_fraction_of_peak": 0.10,
    },
    "required_outputs": [
        "ELM crash amplitude",
        "ELM energy loss per event",
        "peak divertor heat flux",
        "wetted area",
        "ELM frequency",
        "stability window shift",
    ],
    "still_missing": [
        "actual JOREK equilibrium file or include",
        "actual JOREK profile block syntax",
        "actual JOREK boundary/divertor keywords",
        "actual diagnostic variable names",
    ],
}

json_out.write_text(json.dumps(pseudo, indent=2), encoding="utf-8")

md = f"""# case_A_pseudoreconstruction

## Purpose
Paper-faithful pseudo-reconstruction of a JOREK realistic X-point multi-ELM-cycle baseline.

## Published anchors
- primary: PRL_2015_multi_ELM_cycle
- secondary: RMP_multi_ELM_mitigation_case
- heat_flux_anchor: JET_ILW_JPN83334_wall_aligned_grid_case

## Identity
- device_style: {pseudo["identity"]["device_style"]}
- geometry_type: {pseudo["identity"]["geometry_type"]}
- regime: {pseudo["identity"]["regime"]}
- model_scope: {pseudo["identity"]["model_scope"]}

## Geometry assumptions
- R0_m: {pseudo["geometry_assumptions"]["R0_m"]}
- a_m: {pseudo["geometry_assumptions"]["a_m"]}
- kappa: {pseudo["geometry_assumptions"]["kappa"]}
- delta: {pseudo["geometry_assumptions"]["delta"]}
- xpoint_config: {pseudo["geometry_assumptions"]["xpoint_config"]}
- q95_target: {pseudo["geometry_assumptions"]["q95_target"]}

## Profile assumptions
### Density
- shape: {pseudo["profile_assumptions"]["density"]["shape"]}
- core_n20: {pseudo["profile_assumptions"]["density"]["core_n20"]}
- pedestal_n20: {pseudo["profile_assumptions"]["density"]["pedestal_n20"]}
- edge_n20: {pseudo["profile_assumptions"]["density"]["edge_n20"]}

### Temperature
- shape: {pseudo["profile_assumptions"]["temperature"]["shape"]}
- core_keV: {pseudo["profile_assumptions"]["temperature"]["core_keV"]}
- pedestal_keV: {pseudo["profile_assumptions"]["temperature"]["pedestal_keV"]}
- edge_keV: {pseudo["profile_assumptions"]["temperature"]["edge_keV"]}
- Ti_equals_Te_first_pass: {pseudo["profile_assumptions"]["temperature"]["Ti_equals_Te_first_pass"]}

### Pressure/current intent
- pedestal_pressure_gradient_setting: {pseudo["profile_assumptions"]["pressure"]["pedestal_pressure_gradient_setting"]}
- edge_current_gradient_setting: {pseudo["profile_assumptions"]["current"]["edge_current_gradient_setting"]}
- bootstrap_fraction_guess: {pseudo["profile_assumptions"]["current"]["bootstrap_fraction_guess"]}

## Flow and control assumptions
- toroidal_flow_profile: {pseudo["flow_and_control_assumptions"]["toroidal_flow_profile"]}
- poloidal_flow_profile: {pseudo["flow_and_control_assumptions"]["poloidal_flow_profile"]}
- edge_shear_definition: {pseudo["flow_and_control_assumptions"]["edge_shear_definition"]}
- tct_surrogate_definition: {pseudo["flow_and_control_assumptions"]["tct_surrogate_definition"]}

## Physics switches
- reduced_mhd: {pseudo["physics_switches"]["reduced_mhd"]}
- two_fluid: {pseudo["physics_switches"]["two_fluid"]}
- diamagnetic_effects: {pseudo["physics_switches"]["diamagnetic_effects"]}
- neoclassical_flow: {pseudo["physics_switches"]["neoclassical_flow"]}
- resistive_wall: {pseudo["physics_switches"]["resistive_wall"]}
- sheath_boundary_conditions: {pseudo["physics_switches"]["sheath_boundary_conditions"]}
- sol_divertor_treatment: {pseudo["physics_switches"]["sol_divertor_treatment"]}

## Numerics
- toroidal_harmonics: {pseudo["numerics"]["toroidal_harmonics"]}
- time_step_value: {pseudo["numerics"]["time_step_value"]} {pseudo["numerics"]["time_step_units"]}
- total_runtime_value: {pseudo["numerics"]["total_runtime_value"]} {pseudo["numerics"]["total_runtime_units"]}
- output_cadence_value: {pseudo["numerics"]["output_cadence_value"]} {pseudo["numerics"]["output_cadence_units"]}
- checkpoint_cadence_value: {pseudo["numerics"]["checkpoint_cadence_value"]} {pseudo["numerics"]["checkpoint_cadence_units"]}

## Boundary and divertor
- boundary_strategy: {pseudo["boundary_and_divertor"]["boundary_strategy"]}
- divertor_representation: {pseudo["boundary_and_divertor"]["divertor_representation"]}
- sol_model: {pseudo["boundary_and_divertor"]["sol_model"]}
- sheath_bc: {pseudo["boundary_and_divertor"]["sheath_bc"]}
- target_surface: {pseudo["boundary_and_divertor"]["target_surface"]}
- peak_heat_flux_statistic: {pseudo["boundary_and_divertor"]["peak_heat_flux_statistic"]}
- wetted_area_threshold_fraction_of_peak: {pseudo["boundary_and_divertor"]["wetted_area_threshold_fraction_of_peak"]}

## Still missing
"""
for item in pseudo["still_missing"]:
    md += f"- {item}\n"

md_out.write_text(md, encoding="utf-8")

print("Wrote:")
print(" -", json_out)
print(" -", md_out)
