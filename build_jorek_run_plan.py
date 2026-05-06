import csv
import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

matrix_json = PKG / "jorek_case_matrix.json"
workbook_json = PKG / "jorek_case_workbook_merged.json"
config_json = PKG / "jorek_firstpass_config_filled.json"

out_json = PKG / "jorek_run_plan.json"
out_md = PKG / "jorek_run_plan.md"
out_csv = PKG / "jorek_run_plan.csv"

required = [matrix_json, workbook_json, config_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with matrix_json.open("r", encoding="utf-8") as f:
    matrix = json.load(f)

with workbook_json.open("r", encoding="utf-8") as f:
    workbook = json.load(f)

with config_json.open("r", encoding="utf-8") as f:
    config = json.load(f)

wb_by_case = {row["case_name"]: row for row in workbook}

run_rows = []
for case in matrix["cases"]:
    name = case["case_name"]
    wb = wb_by_case.get(name, {})

    run_rows.append({
        "case_name": name,
        "purpose": case.get("purpose", ""),
        "equilibrium_source": wb.get("equilibrium_source", ""),
        "equilibrium_file": wb.get("equilibrium_file", ""),
        "shot_or_case_id": wb.get("shot_or_case_id", ""),
        "R0_m": wb.get("R0_m", ""),
        "a_m": wb.get("a_m", ""),
        "q95_target": wb.get("q95_target", ""),
        "density_profile_source": wb.get("density_profile_source", ""),
        "temperature_profile_source": wb.get("temperature_profile_source", ""),
        "pressure_profile_source": wb.get("pressure_profile_source", ""),
        "current_profile_source": wb.get("current_profile_source", ""),
        "edge_drive_level": wb.get("edge_drive_level", ""),
        "pedestal_pressure_gradient_setting": wb.get("pedestal_pressure_gradient_setting", ""),
        "edge_current_gradient_setting": wb.get("edge_current_gradient_setting", ""),
        "toroidal_flow_profile": wb.get("toroidal_flow_profile", ""),
        "poloidal_flow_profile": wb.get("poloidal_flow_profile", ""),
        "edge_shear_definition": wb.get("edge_shear_definition", ""),
        "tct_surrogate_definition": wb.get("tct_surrogate_definition", ""),
        "reduced_mhd": config["physics_switches"]["reduced_mhd"],
        "two_fluid": config["physics_switches"]["two_fluid"],
        "diamagnetic_effects": config["physics_switches"]["diamagnetic_effects"],
        "neoclassical_flow": config["physics_switches"]["neoclassical_flow"],
        "resistive_wall": config["physics_switches"]["resistive_wall"],
        "sheath_boundary_conditions": config["physics_switches"]["sheath_boundary_conditions"],
        "sol_divertor_treatment": config["physics_switches"]["sol_divertor_treatment"],
        "mesh_plan": config["numerics"]["mesh_plan"],
        "toroidal_harmonics": config["numerics"]["toroidal_harmonics"],
        "time_step_strategy": config["numerics"]["time_step_strategy"],
        "total_runtime_strategy": config["numerics"]["total_runtime_strategy"],
        "output_cadence": config["numerics"]["output_cadence"],
        "restart_strategy": config["numerics"]["restart_strategy"],
        "extract_elm_crash_amplitude": "required",
        "extract_elm_energy_loss_per_event": "required",
        "extract_peak_divertor_heat_flux": "required",
        "extract_wetted_area": "required",
        "extract_elm_frequency": "required",
        "extract_stability_window_shift": "required",
        "launch_ready": "no",
        "launch_blockers": (
            "Need accepted equilibrium/profile source, explicit boundary/divertor choice, "
            "explicit mesh/timestep values, and postprocessing methods."
        ),
    })

with out_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=run_rows[0].keys())
    writer.writeheader()
    writer.writerows(run_rows)

bundle = {
    "frozen_reference": config["frozen_reference"],
    "physics_switches": config["physics_switches"],
    "numerics": config["numerics"],
    "required_outputs": config["postprocessing"],
    "cases": run_rows,
}
with out_json.open("w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)

md = []
md.append("# JOREK Run Plan")
md.append("")
md.append("## Frozen reference")
fr = config["frozen_reference"]
for k, v in fr.items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Physics switches")
for k, v in config["physics_switches"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Numerics")
for k, v in config["numerics"].items():
    md.append(f"- {k}: {v}")
md.append("")
for row in run_rows:
    md.append(f"## {row['case_name']}")
    for k, v in row.items():
        if k == "case_name":
            continue
        md.append(f"- {k}: {v}")
    md.append("")

out_md.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
print(" -", out_csv)
