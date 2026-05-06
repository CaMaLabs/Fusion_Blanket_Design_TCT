import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_json = PKG / "jorek_run_plan_merged.json"
out_dir = PKG / "jorek_case_block_templates"
out_dir.mkdir(parents=True, exist_ok=True)

if not run_plan_json.exists():
    raise SystemExit(f"Missing required file: {run_plan_json}")

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

def block_text(case: dict) -> str:
    return f"""# ============================================================
# JOREK CASE TEMPLATE
# Case: {case["case_name"]}
# Purpose: {case["purpose"]}
# Status: template_only_not_runnable
# ============================================================

# ------------------------------------------------------------
# 1. Reference / provenance
# ------------------------------------------------------------
# frozen_reference_name = 55cm_be_outer_kill_mainline
# equilibrium_source = {case.get("equilibrium_source", "")}
# equilibrium_file = {case.get("equilibrium_file", "")}
# shot_or_case_id = {case.get("shot_or_case_id", "")}

# ------------------------------------------------------------
# 2. Geometry / equilibrium
# Replace this section with actual JOREK-compatible equilibrium
# include / syntax taken from your chosen example case.
# ------------------------------------------------------------
[geometry]
R0_m = {case.get("R0_m", "")}
a_m = {case.get("a_m", "")}
q95_target = {case.get("q95_target", "")}
equilibrium_file = TODO_REPLACE_WITH_REAL_INPUT
xpoint_config = TODO_REPLACE
# kappa = TODO_REPLACE
# delta = TODO_REPLACE

# ------------------------------------------------------------
# 3. Profiles
# Replace with actual profile block syntax used by your JOREK base case.
# ------------------------------------------------------------
[profiles]
density_profile_source = {case.get("density_profile_source", "")}
temperature_profile_source = {case.get("temperature_profile_source", "")}
pressure_profile_source = {case.get("pressure_profile_source", "")}
current_profile_source = {case.get("current_profile_source", "")}

density_profile_include = TODO_REPLACE
temperature_profile_include = TODO_REPLACE
pressure_profile_include = TODO_REPLACE
current_profile_include = TODO_REPLACE

# ------------------------------------------------------------
# 4. Case controls / scenario mapping
# ------------------------------------------------------------
[scenario]
edge_drive_level = {case.get("edge_drive_level", "")}
pedestal_pressure_gradient_setting = {case.get("pedestal_pressure_gradient_setting", "")}
edge_current_gradient_setting = {case.get("edge_current_gradient_setting", "")}
toroidal_flow_profile = {case.get("toroidal_flow_profile", "")}
poloidal_flow_profile = {case.get("poloidal_flow_profile", "")}
edge_shear_definition = {case.get("edge_shear_definition", "")}
tct_surrogate_definition = {case.get("tct_surrogate_definition", "")}

# ------------------------------------------------------------
# 5. Physics switches
# Replace with actual JOREK syntax/keywords.
# ------------------------------------------------------------
[physics]
reduced_mhd = {case.get("reduced_mhd", "")}
two_fluid = {case.get("two_fluid", "")}
diamagnetic_effects = {case.get("diamagnetic_effects", "")}
neoclassical_flow = {case.get("neoclassical_flow", "")}
resistive_wall = {case.get("resistive_wall", "")}
sheath_boundary_conditions = {case.get("sheath_boundary_conditions", "")}
sol_divertor_treatment = {case.get("sol_divertor_treatment", "")}

# ------------------------------------------------------------
# 6. Numerics
# Replace with actual JOREK namelist block names and accepted syntax.
# ------------------------------------------------------------
[numerics]
mesh_plan = {case.get("mesh_plan_value", "")}
mesh_plan_note = {case.get("mesh_plan_note", "")}
mesh_refinement_priority = {case.get("mesh_refinement_priority", "")}
toroidal_harmonics = {case.get("toroidal_harmonics_value", "")}
time_step = {case.get("time_step_value", "")}
time_step_units = {case.get("time_step_units", "")}
total_runtime = {case.get("total_runtime_value", "")}
total_runtime_units = {case.get("total_runtime_units", "")}
output_cadence = {case.get("output_cadence_value", "")}
output_cadence_units = {case.get("output_cadence_units", "")}
checkpoint_cadence = {case.get("checkpoint_cadence_value", "")}
checkpoint_cadence_units = {case.get("checkpoint_cadence_units", "")}

# ------------------------------------------------------------
# 7. Boundary / divertor
# Replace with actual boundary implementation from chosen JOREK example.
# ------------------------------------------------------------
[boundary]
target_surface = {case.get("target_surface", "")}
peak_heat_flux_statistic = {case.get("peak_heat_flux_statistic", "")}
wetted_area_threshold_fraction_of_peak = {case.get("wetted_area_threshold_fraction_of_peak", "")}
heat_flux_normalization_note = {case.get("heat_flux_normalization_note", "")}

boundary_strategy = TODO_REPLACE
divertor_representation = TODO_REPLACE
sol_model = TODO_REPLACE
sheath_bc = TODO_REPLACE

# ------------------------------------------------------------
# 8. Diagnostics / outputs
# Replace with actual variable names / output settings.
# ------------------------------------------------------------
[diagnostics]
extract_elm_crash_amplitude = {case.get("extract_elm_crash_amplitude", "")}
extract_elm_energy_loss_per_event = {case.get("extract_elm_energy_loss_per_event", "")}
extract_peak_divertor_heat_flux = {case.get("extract_peak_divertor_heat_flux", "")}
extract_wetted_area = {case.get("extract_wetted_area", "")}
extract_elm_frequency = {case.get("extract_elm_frequency", "")}
extract_stability_window_shift = {case.get("extract_stability_window_shift", "")}

event_detector_primary = {case.get("event_detector_primary", "")}
event_amplitude_threshold = {case.get("event_amplitude_threshold", "")}
heat_pulse_threshold = {case.get("heat_pulse_threshold", "")}
minimum_event_separation_steps = {case.get("minimum_event_separation_steps", "")}

# ------------------------------------------------------------
# 9. Launch blockers
# ------------------------------------------------------------
# launch_ready = {case.get("launch_ready", "")}
# launch_blockers = {case.get("launch_blockers", "")}

# ------------------------------------------------------------
# 10. Notes
# ------------------------------------------------------------
# case_specific_override_notes = {case.get("case_specific_override_notes", "")}
"""

index = []

for case in run_plan["cases"]:
    case_name = case["case_name"]
    path = out_dir / f"{case_name}.template"
    path.write_text(block_text(case), encoding="utf-8")
    index.append({
        "case_name": case_name,
        "template_file": str(path),
    })

index_json = out_dir / "index.json"
index_md = out_dir / "README.md"

with index_json.open("w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

readme_lines = [
    "# JOREK Case Block Templates",
    "",
    "These are structured per-case template files, not runnable JOREK decks.",
    "Replace placeholder sections with real JOREK syntax from your chosen base/example case.",
    "",
]
for item in index:
    readme_lines.append(f'- {item["case_name"]}: {item["template_file"]}')

index_md.write_text("\n".join(readme_lines), encoding="utf-8")

print("Wrote:")
print(" -", index_json)
print(" -", index_md)
for item in index:
    print(" -", item["template_file"])

