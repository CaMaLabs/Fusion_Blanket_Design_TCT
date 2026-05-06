import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
OUT = ROOT / "jorek_campaign_package"
OUT.mkdir(parents=True, exist_ok=True)

# Frozen engineering reference from the current best basin
reference = {
    "reference_name": "55cm_be_outer_kill_mainline",
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
}

# Synthetic equilibrium assumptions.
# These are placeholders to seed case construction, not validated reactor inputs.
equilibrium = {
    "type": "synthetic_first_pass",
    "notes": [
        "This is a synthetic startup equilibrium, not a real EFIT or experimental reconstruction.",
        "Use only to seed JOREK case construction and workbook completion.",
        "Replace with real equilibrium data when available.",
    ],
    "geometry": {
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
    },
    "magnetic": {
        "Bt_T": 5.3,
        "Ip_MA": 9.0,
        "q95_target": 3.5,
        "q_axis_estimate": 1.1,
        "betaN_target": 2.2,
    },
    "edge_control_context": {
        "edge_drive_nominal": 0.70,
        "best_reduced_basin": {
            "edge_drive": [0.65, 0.70],
            "v_tor": [0.65, 0.75],
            "v_pol": [0.20, 0.30],
            "tct_gain": [0.65, 0.75],
        },
    },
}

# Synthetic profiles, normalized and annotated.
profiles = {
    "type": "synthetic_first_pass_profiles",
    "notes": [
        "These are shape assumptions for first-pass case setup.",
        "Values are normalized or nominal placeholders where appropriate.",
        "Replace with real fitted profiles before claiming physical validation.",
    ],
    "density_profile": {
        "source": "synthetic",
        "shape": "core-flat pedestal-drop",
        "core_n20": 1.0,
        "pedestal_n20": 0.75,
        "edge_n20": 0.30,
        "normalization_notes": "Units shown as 1e20 m^-3 style placeholders.",
    },
    "temperature_profile": {
        "source": "synthetic",
        "shape": "hot core / steep pedestal / cool edge",
        "core_keV": 12.0,
        "pedestal_keV": 2.2,
        "edge_keV": 0.20,
        "electron_ion_relation": "Ti ~= Te first-pass assumption",
    },
    "pressure_profile": {
        "source": "derived_from_density_and_temperature",
        "shape": "consistent_with_nominal_edge_drive",
        "pedestal_gradient_case_A_B": "baseline_high_drive",
        "pedestal_gradient_case_C_D": "baseline_or_shaped_stabilized_surrogate",
    },
    "current_profile": {
        "source": "synthetic",
        "shape": "monotonic core current with edge-current shoulder",
        "bootstrap_fraction_guess": 0.30,
        "edge_current_gradient_case_A_B": "baseline_high_drive",
        "edge_current_gradient_case_C_D": "baseline_or_shaped_stabilized_surrogate",
    },
}

# Synthetic flow definitions tied to reduced-model findings.
flows = {
    "type": "synthetic_first_pass_flows",
    "notes": [
        "These are scenario labels plus nominal normalized values for case seeding.",
        "Use these to populate the JOREK workbook and case matrix, not as final validated profiles.",
    ],
    "levels": {
        "toroidal_flow": {
            "low": {
                "normalized_peak": 0.20,
                "description": "baseline low toroidal rotation profile"
            },
            "high": {
                "normalized_peak": 0.70,
                "description": "high toroidal rotation profile, aligned with reduced-model best basin"
            },
        },
        "poloidal_flow": {
            "low": {
                "normalized_peak": 0.05,
                "description": "baseline low poloidal flow profile"
            },
            "moderate": {
                "normalized_peak": 0.25,
                "description": "moderate poloidal flow profile, mainly to support shear"
            },
        },
        "edge_shear": {
            "low": {
                "description": "derived from low toroidal + low poloidal flow"
            },
            "high": {
                "description": "derived from high toroidal + moderate poloidal flow"
            },
        },
    },
    "tct_surrogate": {
        "low": {
            "type": "profile_or_transport_surrogate",
            "definition": "baseline profile/current-gradient/transport assumptions"
        },
        "high": {
            "type": "profile_or_transport_surrogate",
            "definition": "stronger edge stabilization surrogate via shaped edge profile and/or transport/current-gradient moderation"
        },
    },
}

cases = [
    {
        "case_name": "case_A_baseline_low_control",
        "purpose": "Baseline edge / ELM reference case.",
        "equilibrium_source": "synthetic_first_pass",
        "equilibrium_file": "jorek_synthetic_equilibrium_assumptions.json",
        "shot_or_case_id": "synthetic_55cm_reference",
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
        "q95_target": 3.5,
        "density_profile_source": "jorek_synthetic_profiles.json:density_profile",
        "temperature_profile_source": "jorek_synthetic_profiles.json:temperature_profile",
        "pressure_profile_source": "jorek_synthetic_profiles.json:pressure_profile",
        "current_profile_source": "jorek_synthetic_profiles.json:current_profile",
        "edge_drive_level": "nominal_high",
        "pedestal_pressure_gradient_setting": "baseline_high_drive",
        "edge_current_gradient_setting": "baseline_high_drive",
        "toroidal_flow_level": "low",
        "toroidal_flow_profile": "low",
        "poloidal_flow_level": "low",
        "poloidal_flow_profile": "low",
        "edge_shear_level": "low",
        "edge_shear_definition": "derived from low toroidal + low poloidal flow",
        "tct_surrogate_level": "low",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "tct_surrogate_definition": "baseline profile/current-gradient/transport assumptions",
        "sol_included": "TODO_yes_or_no",
        "divertor_model": "TODO_define",
        "sheath_bc": "TODO_define",
        "resistive_wall_enabled": "TODO_yes_or_no",
        "two_fluid_enabled": "TODO_yes_or_no",
        "diamagnetic_enabled": "TODO_yes_or_no",
        "neoclassical_flow_enabled": "TODO_yes_or_no",
        "mesh_notes": "TODO_define_mesh_and_resolution",
        "toroidal_harmonics": "TODO_define",
        "time_step": "TODO_define",
        "total_sim_time": "TODO_define",
        "output_cadence": "TODO_define",
        "extract_elm_crash_amplitude": "yes",
        "extract_elm_energy_loss": "yes",
        "extract_peak_divertor_heat_flux": "yes",
        "extract_wetted_area": "yes",
        "extract_elm_frequency": "yes",
        "extract_stability_window_shift": "yes",
        "extraction_script_or_method": "TODO_define_postprocessing",
        "status": "synthetic_seed_ready",
        "notes": "First-pass synthetic seed case.",
    },
    {
        "case_name": "case_B_high_flow",
        "purpose": "Higher toroidal flow plus moderate poloidal flow.",
        "equilibrium_source": "synthetic_first_pass",
        "equilibrium_file": "jorek_synthetic_equilibrium_assumptions.json",
        "shot_or_case_id": "synthetic_55cm_reference",
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
        "q95_target": 3.5,
        "density_profile_source": "jorek_synthetic_profiles.json:density_profile",
        "temperature_profile_source": "jorek_synthetic_profiles.json:temperature_profile",
        "pressure_profile_source": "jorek_synthetic_profiles.json:pressure_profile",
        "current_profile_source": "jorek_synthetic_profiles.json:current_profile",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient_setting": "baseline_high_drive",
        "edge_current_gradient_setting": "baseline_high_drive",
        "toroidal_flow_level": "high",
        "toroidal_flow_profile": "high",
        "poloidal_flow_level": "moderate",
        "poloidal_flow_profile": "moderate",
        "edge_shear_level": "high",
        "edge_shear_definition": "derived from high toroidal + moderate poloidal flow",
        "tct_surrogate_level": "low",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "tct_surrogate_definition": "baseline profile/current-gradient/transport assumptions",
        "sol_included": "TODO_yes_or_no",
        "divertor_model": "TODO_define",
        "sheath_bc": "TODO_define",
        "resistive_wall_enabled": "TODO_yes_or_no",
        "two_fluid_enabled": "TODO_yes_or_no",
        "diamagnetic_enabled": "TODO_yes_or_no",
        "neoclassical_flow_enabled": "TODO_yes_or_no",
        "mesh_notes": "TODO_define_mesh_and_resolution",
        "toroidal_harmonics": "TODO_define",
        "time_step": "TODO_define",
        "total_sim_time": "TODO_define",
        "output_cadence": "TODO_define",
        "extract_elm_crash_amplitude": "yes",
        "extract_elm_energy_loss": "yes",
        "extract_peak_divertor_heat_flux": "yes",
        "extract_wetted_area": "yes",
        "extract_elm_frequency": "yes",
        "extract_stability_window_shift": "yes",
        "extraction_script_or_method": "TODO_define_postprocessing",
        "status": "synthetic_seed_ready",
        "notes": "High-flow synthetic seed case.",
    },
    {
        "case_name": "case_C_stabilized_surrogate",
        "purpose": "Baseline flow with stronger stabilization surrogate.",
        "equilibrium_source": "synthetic_first_pass",
        "equilibrium_file": "jorek_synthetic_equilibrium_assumptions.json",
        "shot_or_case_id": "synthetic_55cm_reference",
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
        "q95_target": 3.5,
        "density_profile_source": "jorek_synthetic_profiles.json:density_profile",
        "temperature_profile_source": "jorek_synthetic_profiles.json:temperature_profile",
        "pressure_profile_source": "jorek_synthetic_profiles.json:pressure_profile",
        "current_profile_source": "jorek_synthetic_profiles.json:current_profile",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient_setting": "baseline_or_shaped_stabilized_surrogate",
        "edge_current_gradient_setting": "baseline_or_shaped_stabilized_surrogate",
        "toroidal_flow_level": "low",
        "toroidal_flow_profile": "low",
        "poloidal_flow_level": "low",
        "poloidal_flow_profile": "low",
        "edge_shear_level": "low",
        "edge_shear_definition": "derived from low toroidal + low poloidal flow",
        "tct_surrogate_level": "high",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "tct_surrogate_definition": "stronger edge stabilization surrogate via shaped edge profile and/or transport/current-gradient moderation",
        "sol_included": "TODO_yes_or_no",
        "divertor_model": "TODO_define",
        "sheath_bc": "TODO_define",
        "resistive_wall_enabled": "TODO_yes_or_no",
        "two_fluid_enabled": "TODO_yes_or_no",
        "diamagnetic_enabled": "TODO_yes_or_no",
        "neoclassical_flow_enabled": "TODO_yes_or_no",
        "mesh_notes": "TODO_define_mesh_and_resolution",
        "toroidal_harmonics": "TODO_define",
        "time_step": "TODO_define",
        "total_sim_time": "TODO_define",
        "output_cadence": "TODO_define",
        "extract_elm_crash_amplitude": "yes",
        "extract_elm_energy_loss": "yes",
        "extract_peak_divertor_heat_flux": "yes",
        "extract_wetted_area": "yes",
        "extract_elm_frequency": "yes",
        "extract_stability_window_shift": "yes",
        "extraction_script_or_method": "TODO_define_postprocessing",
        "status": "synthetic_seed_ready",
        "notes": "High-stabilization synthetic seed case.",
    },
    {
        "case_name": "case_D_combined",
        "purpose": "High flow plus strong stabilization surrogate.",
        "equilibrium_source": "synthetic_first_pass",
        "equilibrium_file": "jorek_synthetic_equilibrium_assumptions.json",
        "shot_or_case_id": "synthetic_55cm_reference",
        "R0_m": 0.55,
        "a_m": 0.55,
        "kappa": 1.70,
        "delta": 0.30,
        "xpoint_config": "lower_single_null",
        "q95_target": 3.5,
        "density_profile_source": "jorek_synthetic_profiles.json:density_profile",
        "temperature_profile_source": "jorek_synthetic_profiles.json:temperature_profile",
        "pressure_profile_source": "jorek_synthetic_profiles.json:pressure_profile",
        "current_profile_source": "jorek_synthetic_profiles.json:current_profile",
        "edge_drive_level": "same_as_A",
        "pedestal_pressure_gradient_setting": "baseline_or_shaped_stabilized_surrogate",
        "edge_current_gradient_setting": "baseline_or_shaped_stabilized_surrogate",
        "toroidal_flow_level": "high",
        "toroidal_flow_profile": "high",
        "poloidal_flow_level": "moderate",
        "poloidal_flow_profile": "moderate",
        "edge_shear_level": "high",
        "edge_shear_definition": "derived from high toroidal + moderate poloidal flow",
        "tct_surrogate_level": "high",
        "tct_surrogate_type": "profile_or_transport_surrogate",
        "tct_surrogate_definition": "stronger edge stabilization surrogate combined with high-flow scenario",
        "sol_included": "TODO_yes_or_no",
        "divertor_model": "TODO_define",
        "sheath_bc": "TODO_define",
        "resistive_wall_enabled": "TODO_yes_or_no",
        "two_fluid_enabled": "TODO_yes_or_no",
        "diamagnetic_enabled": "TODO_yes_or_no",
        "neoclassical_flow_enabled": "TODO_yes_or_no",
        "mesh_notes": "TODO_define_mesh_and_resolution",
        "toroidal_harmonics": "TODO_define",
        "time_step": "TODO_define",
        "total_sim_time": "TODO_define",
        "output_cadence": "TODO_define",
        "extract_elm_crash_amplitude": "yes",
        "extract_elm_energy_loss": "yes",
        "extract_peak_divertor_heat_flux": "yes",
        "extract_wetted_area": "yes",
        "extract_elm_frequency": "yes",
        "extract_stability_window_shift": "yes",
        "extraction_script_or_method": "TODO_define_postprocessing",
        "status": "synthetic_seed_ready",
        "notes": "Combined high-flow and high-stabilization synthetic seed case.",
    },
]

notes_md = """# JOREK Synthetic Startup Notes

## What this package is
A synthetic, internally consistent startup pack for JOREK case construction.

## What this package is not
- not a real EFIT
- not a validated machine equilibrium
- not experimental profile data
- not a basis for claiming physical signoff

## Why it exists
To remove the current blocker:
we had no equilibrium/profile source at all.

## Use it for
- filling the workbook
- locking the first 4-case campaign
- deciding what real data still needs to be acquired
- building the first case-construction draft

## Replace first
These fields should be replaced as soon as real data exists:
- equilibrium_source / equilibrium_file
- q95_target if a real equilibrium changes it
- density/temperature/current profiles
- boundary model details
- physics switches
- numerical setup
"""

# Write files
(OUT / "jorek_synthetic_equilibrium_assumptions.json").write_text(
    json.dumps(equilibrium, indent=2),
    encoding="utf-8",
)
(OUT / "jorek_synthetic_profiles.json").write_text(
    json.dumps(profiles, indent=2),
    encoding="utf-8",
)
(OUT / "jorek_synthetic_flows.json").write_text(
    json.dumps(flows, indent=2),
    encoding="utf-8",
)

csv_path = OUT / "jorek_synthetic_case_seed.csv"
fieldnames = list(cases[0].keys())
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cases)

(OUT / "jorek_synthetic_startup_notes.md").write_text(notes_md, encoding="utf-8")

print("Wrote:")
print(" -", OUT / "jorek_synthetic_equilibrium_assumptions.json")
print(" -", OUT / "jorek_synthetic_profiles.json")
print(" -", OUT / "jorek_synthetic_flows.json")
print(" -", csv_path)
print(" -", OUT / "jorek_synthetic_startup_notes.md")
