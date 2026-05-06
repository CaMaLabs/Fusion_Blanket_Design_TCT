import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_path = PKG / "jorek_run_plan_merged.json"
pseudo_path = PKG / "runs" / "case_A_baseline_low_control" / "case_A_pseudoreconstruction.json"

out_json = PKG / "jorek_run_plan_final.json"
out_md = PKG / "jorek_run_plan_final.md"

required = [run_plan_path, pseudo_path]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with run_plan_path.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

with pseudo_path.open("r", encoding="utf-8") as f:
    pseudo = json.load(f)

new_cases = []
for case in run_plan["cases"]:
    if case["case_name"] != "case_A_baseline_low_control":
        new_cases.append(case)
        continue

    merged = dict(case)

    merged["purpose"] = pseudo["purpose"]

    merged["equilibrium_source"] = "published_case_reconstruction_synthetic_first_pass"
    merged["equilibrium_file"] = "TODO_replace_with_real_JOREK_equilibrium_or_example_input"
    merged["shot_or_case_id"] = "published_anchor_PRL_2015_multi_ELM_cycle"

    merged["R0_m"] = pseudo["geometry_assumptions"]["R0_m"]
    merged["a_m"] = pseudo["geometry_assumptions"]["a_m"]
    merged["q95_target"] = pseudo["geometry_assumptions"]["q95_target"]

    merged["density_profile_source"] = "jorek_synthetic_profiles.json:density_profile"
    merged["temperature_profile_source"] = "jorek_synthetic_profiles.json:temperature_profile"
    merged["pressure_profile_source"] = "jorek_synthetic_profiles.json:pressure_profile"
    merged["current_profile_source"] = "jorek_synthetic_profiles.json:current_profile"

    merged["edge_drive_level"] = "nominal_high"
    merged["pedestal_pressure_gradient_setting"] = pseudo["profile_assumptions"]["pressure"]["pedestal_pressure_gradient_setting"]
    merged["edge_current_gradient_setting"] = pseudo["profile_assumptions"]["current"]["edge_current_gradient_setting"]

    merged["toroidal_flow_profile"] = pseudo["flow_and_control_assumptions"]["toroidal_flow_profile"]
    merged["poloidal_flow_profile"] = pseudo["flow_and_control_assumptions"]["poloidal_flow_profile"]
    merged["edge_shear_definition"] = pseudo["flow_and_control_assumptions"]["edge_shear_definition"]
    merged["tct_surrogate_definition"] = pseudo["flow_and_control_assumptions"]["tct_surrogate_definition"]

    merged["reduced_mhd"] = pseudo["physics_switches"]["reduced_mhd"]
    merged["two_fluid"] = pseudo["physics_switches"]["two_fluid"]
    merged["diamagnetic_effects"] = pseudo["physics_switches"]["diamagnetic_effects"]
    merged["neoclassical_flow"] = pseudo["physics_switches"]["neoclassical_flow"]
    merged["resistive_wall"] = pseudo["physics_switches"]["resistive_wall"]
    merged["sheath_boundary_conditions"] = pseudo["physics_switches"]["sheath_boundary_conditions"]
    merged["sol_divertor_treatment"] = pseudo["physics_switches"]["sol_divertor_treatment"]

    merged["mesh_plan_value"] = pseudo["numerics"]["mesh_plan"]
    merged["mesh_plan_note"] = "Paper-faithful pseudo-reconstruction merged from case_A baseline."
    merged["mesh_refinement_priority"] = pseudo["numerics"]["mesh_refinement_priority"]
    merged["toroidal_harmonics_value"] = pseudo["numerics"]["toroidal_harmonics"]
    merged["time_step_value"] = pseudo["numerics"]["time_step_value"]
    merged["time_step_units"] = pseudo["numerics"]["time_step_units"]
    merged["total_runtime_value"] = pseudo["numerics"]["total_runtime_value"]
    merged["total_runtime_units"] = pseudo["numerics"]["total_runtime_units"]
    merged["output_cadence_value"] = pseudo["numerics"]["output_cadence_value"]
    merged["output_cadence_units"] = pseudo["numerics"]["output_cadence_units"]
    merged["checkpoint_cadence_value"] = pseudo["numerics"]["checkpoint_cadence_value"]
    merged["checkpoint_cadence_units"] = pseudo["numerics"]["checkpoint_cadence_units"]

    merged["target_surface"] = pseudo["boundary_and_divertor"]["target_surface"]
    merged["peak_heat_flux_statistic"] = pseudo["boundary_and_divertor"]["peak_heat_flux_statistic"]
    merged["wetted_area_threshold_fraction_of_peak"] = pseudo["boundary_and_divertor"]["wetted_area_threshold_fraction_of_peak"]
    merged["heat_flux_normalization_note"] = (
        "Published-anchor pseudo-reconstruction baseline; use same heat-flux convention across all cases."
    )

    merged["event_detector_primary"] = "elm_crash_amplitude_trace"
    merged["event_amplitude_threshold"] = 0.15
    merged["heat_pulse_threshold"] = 0.20
    merged["minimum_event_separation_steps"] = 100

    merged["case_specific_override_notes"] = (
        "Merged from case_A_pseudoreconstruction.json. "
        "This is the paper-faithful baseline anchor for the campaign."
    )

    merged["launch_ready"] = "no"
    merged["launch_blockers"] = (
        "Still missing real JOREK syntax, real equilibrium/profile includes, "
        "actual boundary/divertor keywords, and actual diagnostic variable names."
    )

    new_cases.append(merged)

final_bundle = dict(run_plan)
final_bundle["cases"] = new_cases
final_bundle["case_A_anchor"] = {
    "published_anchor": pseudo["published_anchor"],
    "identity": pseudo["identity"],
}

with out_json.open("w", encoding="utf-8") as f:
    json.dump(final_bundle, f, indent=2)

md = []
md.append("# JOREK Run Plan Final")
md.append("")
md.append("## Case A anchor")
md.append(f"- primary: {pseudo['published_anchor']['primary']}")
md.append(f"- secondary: {pseudo['published_anchor']['secondary']}")
md.append(f"- heat_flux_anchor: {pseudo['published_anchor']['heat_flux_anchor']}")
md.append("")
md.append("## Case A identity")
for k, v in pseudo["identity"].items():
    md.append(f"- {k}: {v}")
md.append("")
for case in final_bundle["cases"]:
    md.append(f"## {case['case_name']}")
    for k, v in case.items():
        if k == "case_name":
            continue
        md.append(f"- {k}: {v}")
    md.append("")

out_md.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
