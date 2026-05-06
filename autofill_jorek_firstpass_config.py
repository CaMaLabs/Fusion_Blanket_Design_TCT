import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

config_json = PKG / "jorek_firstpass_config.json"
matrix_json = PKG / "jorek_case_matrix.json"
workbook_json = PKG / "jorek_case_workbook_merged.json"

out_json = PKG / "jorek_firstpass_config_filled.json"
out_md = PKG / "jorek_firstpass_config_filled.md"

required = [config_json, matrix_json, workbook_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\\n" + "\\n".join(missing))

with config_json.open("r", encoding="utf-8") as f:
    config = json.load(f)

with matrix_json.open("r", encoding="utf-8") as f:
    matrix = json.load(f)

with workbook_json.open("r", encoding="utf-8") as f:
    workbook = json.load(f)

cases_by_name = {row["case_name"]: row for row in workbook}

filled = {
    "frozen_reference": config["frozen_reference"],
    "provisional_launch_stance": {
        "status": "synthetic_firstpass_case_construction_ready",
        "notes": [
            "This is still not a real JOREK launch deck.",
            "It is a provisional first-pass stance for case construction.",
            "Synthetic equilibrium/profile assumptions are still in use unless replaced."
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
        "impurity_or_radiation_model": False,
    },
    "numerics": {
        "mesh_plan": "moderate_startup_mesh",
        "toroidal_harmonics": "moderate",
        "time_step_strategy": "conservative_adaptive_if_available",
        "total_runtime_strategy": "long_enough_to_capture_recurrent_event_behavior",
        "output_cadence": "high_around_events",
        "restart_strategy": "checkpoint_enabled",
    },
    "postprocessing": {
        "elm_crash_amplitude": "required",
        "elm_energy_loss_per_event": "required",
        "peak_divertor_heat_flux": "required",
        "wetted_area": "required",
        "elm_frequency": "required",
        "stability_window_shift": "required",
        "method_status": "not_yet_defined",
    },
    "case_interpretations": {},
    "remaining_blockers": config["launch_blockers_remaining"],
}

def case_summary(case_name: str):
    row = cases_by_name.get(case_name, {})
    return {
        "purpose": row.get("purpose", ""),
        "edge_drive_level": row.get("edge_drive_level", ""),
        "pedestal_pressure_gradient_setting": row.get("pedestal_pressure_gradient_setting", ""),
        "edge_current_gradient_setting": row.get("edge_current_gradient_setting", ""),
        "toroidal_flow_profile": row.get("toroidal_flow_profile", ""),
        "poloidal_flow_profile": row.get("poloidal_flow_profile", ""),
        "edge_shear_definition": row.get("edge_shear_definition", ""),
        "tct_surrogate_definition": row.get("tct_surrogate_definition", ""),
        "equilibrium_source": row.get("equilibrium_source", ""),
        "density_profile_source": row.get("density_profile_source", ""),
        "temperature_profile_source": row.get("temperature_profile_source", ""),
        "current_profile_source": row.get("current_profile_source", ""),
        "status": row.get("status", ""),
        "notes": row.get("notes", ""),
    }

for case_name in [
    "case_A_baseline_low_control",
    "case_B_high_flow",
    "case_C_stabilized_surrogate",
    "case_D_combined",
]:
    filled["case_interpretations"][case_name] = case_summary(case_name)

with out_json.open("w", encoding="utf-8") as f:
    json.dump(filled, f, indent=2)

md = []
md.append("# JOREK First-Pass Config Filled")
md.append("")
md.append("## Provisional launch stance")
md.append("- status: synthetic_firstpass_case_construction_ready")
md.append("- still using synthetic seed inputs unless replaced")
md.append("- not yet a runnable JOREK input deck")
md.append("")
md.append("## Frozen reference")
fr = filled["frozen_reference"]
md.append(f'- reference_name: {fr["reference_name"]}')
md.append(f'- radius_cm: {fr["radius_cm"]}')
md.append(f'- R_m: {fr["R_m"]}')
md.append(f'- a_m: {fr["a_m"]}')
md.append(f'- li_current: {fr["li_current"]}')
md.append(f'- tct_supervisor: {fr["tct_supervisor"]}')
md.append(f'- severity_scale: {fr["severity_scale"]}')
md.append("")
md.append("## Physics switches")
for k, v in filled["physics_switches"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Numerics")
for k, v in filled["numerics"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Postprocessing")
for k, v in filled["postprocessing"].items():
    md.append(f"- {k}: {v}")
md.append("")

for case_name, info in filled["case_interpretations"].items():
    md.append(f"## {case_name}")
    for k, v in info.items():
        md.append(f"- {k}: {v}")
    md.append("")

md.append("## Remaining blockers")
for x in filled["remaining_blockers"]:
    md.append(f"- {x}")
md.append("")
md.append("## Immediate meaning")
md.append("- Case construction stance is now provisionally filled.")
md.append("- You still need real or consciously accepted synthetic equilibrium/profile choices.")
md.append("- You still need explicit postprocessing methods.")
md.append("- You still need concrete numerical values before a real launch.")

out_md.write_text("\\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
