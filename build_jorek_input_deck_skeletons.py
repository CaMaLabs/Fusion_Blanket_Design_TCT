import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_json = PKG / "jorek_run_plan_merged.json"
boundary_json = PKG / "jorek_boundary_postprocess_sheet.json"

out_dir = PKG / "jorek_input_deck_skeletons"
out_dir.mkdir(parents=True, exist_ok=True)

required = [run_plan_json, boundary_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

with boundary_json.open("r", encoding="utf-8") as f:
    boundary = json.load(f)

boundary_stance = boundary.get("recommended_boundary_stance", {})
post = boundary.get("recommended_postprocessing_stance", {})

summary = {
    "generated_from": {
        "run_plan": str(run_plan_json),
        "boundary_postprocess": str(boundary_json),
    },
    "cases": [],
}

for case in run_plan["cases"]:
    case_name = case["case_name"]

    deck = {
        "case_name": case_name,
        "purpose": case.get("purpose", ""),
        "status": "skeleton_only_not_launchable",
        "frozen_reference": run_plan.get("frozen_reference", {}),
        "input_sources": {
            "equilibrium_source": case.get("equilibrium_source", ""),
            "equilibrium_file": case.get("equilibrium_file", ""),
            "shot_or_case_id": case.get("shot_or_case_id", ""),
            "density_profile_source": case.get("density_profile_source", ""),
            "temperature_profile_source": case.get("temperature_profile_source", ""),
            "pressure_profile_source": case.get("pressure_profile_source", ""),
            "current_profile_source": case.get("current_profile_source", ""),
        },
        "geometry": {
            "R0_m": case.get("R0_m", ""),
            "a_m": case.get("a_m", ""),
            "q95_target": case.get("q95_target", ""),
        },
        "case_controls": {
            "edge_drive_level": case.get("edge_drive_level", ""),
            "pedestal_pressure_gradient_setting": case.get("pedestal_pressure_gradient_setting", ""),
            "edge_current_gradient_setting": case.get("edge_current_gradient_setting", ""),
            "toroidal_flow_profile": case.get("toroidal_flow_profile", ""),
            "poloidal_flow_profile": case.get("poloidal_flow_profile", ""),
            "edge_shear_definition": case.get("edge_shear_definition", ""),
            "tct_surrogate_definition": case.get("tct_surrogate_definition", ""),
        },
        "physics_switches": {
            "reduced_mhd": case.get("reduced_mhd", ""),
            "two_fluid": case.get("two_fluid", ""),
            "diamagnetic_effects": case.get("diamagnetic_effects", ""),
            "neoclassical_flow": case.get("neoclassical_flow", ""),
            "resistive_wall": case.get("resistive_wall", ""),
            "sheath_boundary_conditions": case.get("sheath_boundary_conditions", ""),
            "sol_divertor_treatment": case.get("sol_divertor_treatment", ""),
        },
        "numerics": {
            "mesh_plan": case.get("mesh_plan_value", ""),
            "mesh_plan_note": case.get("mesh_plan_note", ""),
            "mesh_refinement_priority": case.get("mesh_refinement_priority", ""),
            "toroidal_harmonics": case.get("toroidal_harmonics_value", ""),
            "time_step_value": case.get("time_step_value", ""),
            "time_step_units": case.get("time_step_units", ""),
            "total_runtime_value": case.get("total_runtime_value", ""),
            "total_runtime_units": case.get("total_runtime_units", ""),
            "output_cadence_value": case.get("output_cadence_value", ""),
            "output_cadence_units": case.get("output_cadence_units", ""),
            "checkpoint_cadence_value": case.get("checkpoint_cadence_value", ""),
            "checkpoint_cadence_units": case.get("checkpoint_cadence_units", ""),
        },
        "boundary_and_divertor": {
            "boundary_strategy": boundary_stance.get("boundary_strategy", {}),
            "sol_treatment": boundary_stance.get("sol_treatment", {}),
            "divertor_representation": boundary_stance.get("divertor_representation", {}),
            "sheath_boundary_conditions": boundary_stance.get("sheath_boundary_conditions", {}),
            "resistive_wall_model": boundary_stance.get("resistive_wall_model", {}),
            "vacuum_wall_coupling_notes": boundary_stance.get("vacuum_wall_coupling_notes", ""),
        },
        "event_detection": {
            "primary_detector": case.get("event_detector_primary", ""),
            "event_amplitude_threshold": case.get("event_amplitude_threshold", ""),
            "heat_pulse_threshold": case.get("heat_pulse_threshold", ""),
            "minimum_event_separation_steps": case.get("minimum_event_separation_steps", ""),
            "event_detection_why": case.get("event_detection_why", ""),
        },
        "heat_flux_extraction": {
            "target_surface": case.get("target_surface", ""),
            "peak_heat_flux_statistic": case.get("peak_heat_flux_statistic", ""),
            "wetted_area_threshold_fraction_of_peak": case.get("wetted_area_threshold_fraction_of_peak", ""),
            "heat_flux_normalization_note": case.get("heat_flux_normalization_note", ""),
        },
        "required_outputs": {
            k: v.get("status", "") if isinstance(v, dict) else v
            for k, v in post.items()
        },
        "placeholders_to_replace": [
            "actual equilibrium file/path",
            "actual JOREK input syntax/blocks",
            "actual boundary condition implementation",
            "actual diagnostic variable names",
            "actual postprocessing scripts",
        ],
        "launch_blockers": case.get("launch_blockers", ""),
    }

    json_path = out_dir / f"{case_name}.json"
    md_path = out_dir / f"{case_name}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2)

    md = []
    md.append(f"# {case_name}")
    md.append("")
    md.append(f"- purpose: {deck['purpose']}")
    md.append(f"- status: {deck['status']}")
    md.append("")
    md.append("## Input sources")
    for k, v in deck["input_sources"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Geometry")
    for k, v in deck["geometry"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Case controls")
    for k, v in deck["case_controls"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Physics switches")
    for k, v in deck["physics_switches"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Numerics")
    for k, v in deck["numerics"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Boundary and divertor")
    for k, v in deck["boundary_and_divertor"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Event detection")
    for k, v in deck["event_detection"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Heat-flux extraction")
    for k, v in deck["heat_flux_extraction"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Required outputs")
    for k, v in deck["required_outputs"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Placeholders to replace")
    for item in deck["placeholders_to_replace"]:
        md.append(f"- {item}")
    md.append("")
    md.append("## Launch blockers")
    md.append(f"- {deck['launch_blockers']}")

    md_path.write_text("\n".join(md), encoding="utf-8")

    summary["cases"].append({
        "case_name": case_name,
        "json": str(json_path),
        "md": str(md_path),
    })

summary_json = out_dir / "index.json"
summary_md = out_dir / "README.md"

with summary_json.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

readme = ["# JOREK Input Deck Skeletons", ""]
readme.append("Generated per-case skeletons. These are structured launch worksheets, not runnable JOREK decks.")
readme.append("")
for item in summary["cases"]:
    readme.append(f"- {item['case_name']}")
    readme.append(f"  - json: {item['json']}")
    readme.append(f"  - md: {item['md']}")
readme.append("")
readme.append("Replace placeholders with actual equilibrium, profile, boundary, and diagnostic syntax before launch.")

summary_md.write_text("\n".join(readme), encoding="utf-8")

print("Wrote:")
print(" -", summary_json)
print(" -", summary_md)
for item in summary["cases"]:
    print(" -", item["json"])
    print(" -", item["md"])
