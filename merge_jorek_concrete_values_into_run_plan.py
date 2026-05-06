import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_json = PKG / "jorek_run_plan.json"
concrete_json = PKG / "jorek_concrete_values_sheet.json"

out_json = PKG / "jorek_run_plan_merged.json"
out_csv = PKG / "jorek_run_plan_merged.csv"
out_md = PKG / "jorek_run_plan_merged.md"

required = [run_plan_json, concrete_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

with concrete_json.open("r", encoding="utf-8") as f:
    concrete = json.load(f)

numerics = concrete.get("concrete_numerics", {})
event_detection = concrete.get("event_detection", {})
heat_flux = concrete.get("heat_flux_extraction", {})
case_notes = concrete.get("case_specific_value_overrides", {})

merged_cases = []
for case in run_plan["cases"]:
    name = case["case_name"]
    merged = dict(case)

    merged["mesh_plan_value"] = numerics.get("mesh_plan", {}).get("value", "")
    merged["mesh_plan_note"] = numerics.get("mesh_plan", {}).get("details", {}).get("radial_poloidal_mesh_note", "")
    merged["mesh_refinement_priority"] = numerics.get("mesh_plan", {}).get("details", {}).get("refinement_priority", "")

    merged["toroidal_harmonics_value"] = numerics.get("toroidal_harmonics", {}).get("value", "")
    merged["toroidal_harmonics_why"] = numerics.get("toroidal_harmonics", {}).get("why", "")

    merged["time_step_value"] = numerics.get("time_step", {}).get("value", "")
    merged["time_step_units"] = numerics.get("time_step", {}).get("units", "")
    merged["time_step_why"] = numerics.get("time_step", {}).get("why", "")

    merged["total_runtime_value"] = numerics.get("total_runtime", {}).get("value", "")
    merged["total_runtime_units"] = numerics.get("total_runtime", {}).get("units", "")
    merged["total_runtime_why"] = numerics.get("total_runtime", {}).get("why", "")

    merged["output_cadence_value"] = numerics.get("output_cadence", {}).get("value", "")
    merged["output_cadence_units"] = numerics.get("output_cadence", {}).get("units", "")
    merged["output_cadence_why"] = numerics.get("output_cadence", {}).get("why", "")

    merged["checkpoint_cadence_value"] = numerics.get("checkpoint_cadence", {}).get("value", "")
    merged["checkpoint_cadence_units"] = numerics.get("checkpoint_cadence", {}).get("units", "")
    merged["checkpoint_cadence_why"] = numerics.get("checkpoint_cadence", {}).get("why", "")

    merged["event_detector_primary"] = event_detection.get("primary_detector", "")
    merged["event_amplitude_threshold"] = event_detection.get("event_amplitude_threshold", "")
    merged["heat_pulse_threshold"] = event_detection.get("heat_pulse_threshold", "")
    merged["minimum_event_separation_steps"] = event_detection.get("minimum_event_separation_steps", "")
    merged["event_detection_why"] = event_detection.get("why", "")

    merged["target_surface"] = heat_flux.get("target_surface", "")
    merged["peak_heat_flux_statistic"] = heat_flux.get("peak_heat_flux_statistic", "")
    merged["wetted_area_threshold_fraction_of_peak"] = heat_flux.get("wetted_area_threshold_fraction_of_peak", "")
    merged["heat_flux_normalization_note"] = heat_flux.get("normalization_note", "")

    merged["case_specific_override_notes"] = case_notes.get(name, {}).get("notes", "")

    merged["launch_ready"] = "no"
    merged["launch_blockers"] = (
        "Need accepted equilibrium/profile source, explicit boundary/divertor implementation, "
        "actual JOREK variable names for extraction, and confirmed numerical compatibility."
    )

    merged_cases.append(merged)

merged_bundle = {
    "frozen_reference": run_plan.get("frozen_reference", {}),
    "physics_switches": run_plan.get("physics_switches", {}),
    "numerics_summary": concrete.get("concrete_numerics", {}),
    "event_detection": concrete.get("event_detection", {}),
    "heat_flux_extraction": concrete.get("heat_flux_extraction", {}),
    "cases": merged_cases,
    "remaining_non_numeric_blockers": concrete.get("remaining_non_numeric_blockers", []),
}

with out_json.open("w", encoding="utf-8") as f:
    json.dump(merged_bundle, f, indent=2)

fieldnames = list(merged_cases[0].keys())
with out_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(merged_cases)

md = []
md.append("# JOREK Run Plan Merged")
md.append("")
md.append("## Frozen reference")
for k, v in merged_bundle["frozen_reference"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Event detection")
for k, v in merged_bundle["event_detection"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Heat-flux extraction")
for k, v in merged_bundle["heat_flux_extraction"].items():
    md.append(f"- {k}: {v}")
md.append("")
for case in merged_cases:
    md.append(f"## {case['case_name']}")
    for k, v in case.items():
        if k == "case_name":
            continue
        md.append(f"- {k}: {v}")
    md.append("")
md.append("## Remaining non-numeric blockers")
for item in merged_bundle["remaining_non_numeric_blockers"]:
    md.append(f"- {item}")

out_md.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_csv)
print(" -", out_md)
