import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"
PKG.mkdir(parents=True, exist_ok=True)

config_json = PKG / "jorek_firstpass_config_filled.json"
run_plan_json = PKG / "jorek_run_plan.json"
boundary_json = PKG / "jorek_boundary_postprocess_sheet.json"

out_json = PKG / "jorek_concrete_values_sheet.json"
out_md = PKG / "jorek_concrete_values_sheet.md"

required = [config_json, run_plan_json, boundary_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with config_json.open("r", encoding="utf-8") as f:
    config = json.load(f)

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

with boundary_json.open("r", encoding="utf-8") as f:
    boundary = json.load(f)

sheet = {
    "purpose": (
        "Concrete provisional values for first synthetic JOREK case construction. "
        "These are startup values, not final validated production settings."
    ),
    "frozen_reference": config["frozen_reference"],
    "physics_switches": config["physics_switches"],
    "concrete_numerics": {
        "mesh_plan": {
            "value": "startup_mesh_v1",
            "details": {
                "radial_poloidal_mesh_note": "Use a moderate startup mesh suitable for debugging and first trend capture.",
                "refinement_priority": "pedestal_edge_and_divertor_region",
            },
        },
        "toroidal_harmonics": {
            "value": 8,
            "why": "Good first-pass compromise between under-resolution and overcommitting compute."
        },
        "time_step": {
            "value": 1.0e-7,
            "units": "s",
            "why": "Conservative startup timestep for edge-event dynamics."
        },
        "total_runtime": {
            "value": 5.0e-3,
            "units": "s",
            "why": "Long enough to try to capture burst/crash behavior in a synthetic first pass."
        },
        "output_cadence": {
            "value": 50,
            "units": "steps",
            "why": "Dense enough to resolve transient event structure without dumping every step."
        },
        "checkpoint_cadence": {
            "value": 500,
            "units": "steps",
            "why": "Protect partially completed runs."
        },
    },
    "event_detection": {
        "primary_detector": "elm_crash_amplitude_trace",
        "event_amplitude_threshold": 0.15,
        "heat_pulse_threshold": 0.20,
        "minimum_event_separation_steps": 100,
        "why": (
            "Use one event detector rule across A/B/C/D. "
            "Thresholds are provisional and should be revised after first synthetic outputs."
        ),
    },
    "heat_flux_extraction": {
        "target_surface": "divertor_target_primary",
        "peak_heat_flux_statistic": "max_over_target_and_time",
        "wetted_area_threshold_fraction_of_peak": 0.10,
        "normalization_note": (
            "Use the same target surface and same wetted-area threshold rule across all cases."
        ),
    },
    "case_specific_value_overrides": {
        "case_A_baseline_low_control": {
            "notes": "Use baseline low-flow / low-surrogate settings with no numeric overrides."
        },
        "case_B_high_flow": {
            "notes": "Same numerics as A; only flow-related setup changes."
        },
        "case_C_stabilized_surrogate": {
            "notes": "Same numerics as A; only stabilization-surrogate/profile changes."
        },
        "case_D_combined": {
            "notes": "Same numerics as A; combine high-flow and high-surrogate setup."
        },
    },
    "remaining_non_numeric_blockers": [
        "exact equilibrium file or accepted synthetic equivalent",
        "exact boundary implementation compatible with chosen JOREK setup",
        "exact postprocessing variable names/paths from actual output files",
    ],
}

md = []
md.append("# JOREK Concrete Values Sheet")
md.append("")
md.append("## Purpose")
md.append("Provisional startup values for first synthetic JOREK case construction.")
md.append("These are not final validated production settings.")
md.append("")
md.append("## Frozen reference")
for k, v in sheet["frozen_reference"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Physics switches")
for k, v in sheet["physics_switches"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Concrete numerics")
for k, v in sheet["concrete_numerics"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Event detection")
for k, v in sheet["event_detection"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Heat-flux extraction")
for k, v in sheet["heat_flux_extraction"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Case-specific notes")
for case_name, info in sheet["case_specific_value_overrides"].items():
    md.append(f"### {case_name}")
    for k, v in info.items():
        md.append(f"- {k}: {v}")
    md.append("")
md.append("## Remaining non-numeric blockers")
for item in sheet["remaining_non_numeric_blockers"]:
    md.append(f"- {item}")

with out_json.open("w", encoding="utf-8") as f:
    json.dump(sheet, f, indent=2)

out_md.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
