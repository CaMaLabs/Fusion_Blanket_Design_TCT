import csv
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

infile = PKG / "jorek_case_workbook.csv"
outfile = PKG / "jorek_case_workbook_prefilled.csv"

if not infile.exists():
    raise SystemExit(f"Missing workbook: {infile}")

rows = []
with infile.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        case = row["case_name"]

        # Frozen reference values
        row["R0_m"] = "0.55"
        row["a_m"] = "0.55"

        # Known from current project state
        row["equilibrium_source"] = "TODO_real_equilibrium_or_synthetic_reference"
        row["equilibrium_file"] = "TODO"
        row["shot_or_case_id"] = "TODO"
        row["q95_target"] = "TODO_from_equilibrium"

        row["density_profile_source"] = "TODO_profile_source"
        row["temperature_profile_source"] = "TODO_profile_source"
        row["pressure_profile_source"] = "TODO_derived_or_source"
        row["current_profile_source"] = "TODO_profile_source"

        row["density_profile_notes"] = "Use pedestal-consistent edge profile for JOREK baseline."
        row["temperature_profile_notes"] = "Use edge/pedestal temperature profile consistent with chosen equilibrium."
        row["pressure_profile_notes"] = "Represents reduced-model edge_drive surrogate."
        row["current_profile_notes"] = "Edge current gradient should encode peeling-ballooning drive scenario."

        # Case-specific flow suggestions from reduced-model results
        if case == "case_A_baseline_low_control":
            row["toroidal_flow_profile"] = "low_flow_baseline_profile"
            row["poloidal_flow_profile"] = "low_flow_baseline_profile"
            row["edge_shear_definition"] = "derived_low_shear_from_low_tor_and_low_pol_flow"
            row["tct_surrogate_type"] = "profile_or_transport_surrogate"
            row["tct_surrogate_definition"] = "low surrogate: baseline profile/current-gradient/transport assumptions"
            row["pedestal_pressure_gradient_setting"] = "baseline_high_drive"
            row["edge_current_gradient_setting"] = "baseline_high_drive"

        elif case == "case_B_high_flow":
            row["toroidal_flow_profile"] = "high_toroidal_flow_profile"
            row["poloidal_flow_profile"] = "moderate_poloidal_flow_profile"
            row["edge_shear_definition"] = "derived_high_shear_from_high_tor_and_moderate_pol_flow"
            row["tct_surrogate_type"] = "profile_or_transport_surrogate"
            row["tct_surrogate_definition"] = "low surrogate: same as baseline"
            row["pedestal_pressure_gradient_setting"] = "baseline_high_drive"
            row["edge_current_gradient_setting"] = "baseline_high_drive"

        elif case == "case_C_stabilized_surrogate":
            row["toroidal_flow_profile"] = "low_flow_baseline_profile"
            row["poloidal_flow_profile"] = "low_flow_baseline_profile"
            row["edge_shear_definition"] = "derived_low_shear_from_low_tor_and_low_pol_flow"
            row["tct_surrogate_type"] = "profile_or_transport_surrogate"
            row["tct_surrogate_definition"] = (
                "high surrogate: adjusted edge profile / transport / current-gradient control "
                "representing stronger TCT-like stabilization effect"
            )
            row["pedestal_pressure_gradient_setting"] = "baseline_or_shaped_for_stabilization_surrogate"
            row["edge_current_gradient_setting"] = "baseline_or_shaped_for_stabilization_surrogate"

        elif case == "case_D_combined":
            row["toroidal_flow_profile"] = "high_toroidal_flow_profile"
            row["poloidal_flow_profile"] = "moderate_poloidal_flow_profile"
            row["edge_shear_definition"] = "derived_high_shear_from_high_tor_and_moderate_pol_flow"
            row["tct_surrogate_type"] = "profile_or_transport_surrogate"
            row["tct_surrogate_definition"] = (
                "high surrogate: adjusted edge profile / transport / current-gradient control "
                "combined with high-flow scenario"
            )
            row["pedestal_pressure_gradient_setting"] = "baseline_or_shaped_for_stabilization_surrogate"
            row["edge_current_gradient_setting"] = "baseline_or_shaped_for_stabilization_surrogate"

        # Boundary / physics defaults: still placeholders, but structured
        row["sol_included"] = "TODO_yes_or_no"
        row["divertor_model"] = "TODO_define"
        row["sheath_bc"] = "TODO_define"
        row["resistive_wall_enabled"] = "TODO_yes_or_no"
        row["two_fluid_enabled"] = "TODO_yes_or_no"
        row["diamagnetic_enabled"] = "TODO_yes_or_no"
        row["neoclassical_flow_enabled"] = "TODO_yes_or_no"

        row["mesh_notes"] = "TODO_define_mesh_and_resolution"
        row["toroidal_harmonics"] = "TODO_define"
        row["time_step"] = "TODO_define"
        row["total_sim_time"] = "TODO_define"
        row["output_cadence"] = "TODO_define"

        row["extraction_script_or_method"] = "TODO_define_postprocessing_for_ELM_and_heat_flux_metrics"
        row["status"] = "prefilled_needs_real_inputs"
        row["notes"] = (
            "Auto-prefilled from frozen 55 cm reference and reduced-model case mapping. "
            "Replace TODO fields with real equilibrium/profile/JOREK setup data."
        )

        rows.append(row)

with outfile.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {outfile}")
