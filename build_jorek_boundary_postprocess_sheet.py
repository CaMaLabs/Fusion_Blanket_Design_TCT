import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"
PKG.mkdir(parents=True, exist_ok=True)

config_json = PKG / "jorek_firstpass_config_filled.json"
run_plan_json = PKG / "jorek_run_plan.json"

out_json = PKG / "jorek_boundary_postprocess_sheet.json"
out_md = PKG / "jorek_boundary_postprocess_sheet.md"
out_checklist = PKG / "jorek_boundary_postprocess_checklist.md"

required = [config_json, run_plan_json]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with config_json.open("r", encoding="utf-8") as f:
    config = json.load(f)

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

sheet = {
    "purpose": (
        "First-pass boundary/divertor and postprocessing decision sheet for the "
        "initial 4-case JOREK campaign."
    ),
    "frozen_reference": config["frozen_reference"],
    "recommended_boundary_stance": {
        "boundary_strategy": {
            "value": "first_pass_edge_focused_boundary_set",
            "why": "Keep the first campaign focused on edge-event severity comparisons."
        },
        "sol_treatment": {
            "value": "enabled_if_practical",
            "why": "Desired because peak divertor heat flux and wetted area are core outputs."
        },
        "divertor_representation": {
            "value": "required_for_heat_flux_comparison",
            "why": "You care about divertor loading, so some target/divertor handling is needed."
        },
        "sheath_boundary_conditions": {
            "value": True,
            "why": "Recommended because target heat flux is one of the main success metrics."
        },
        "resistive_wall_model": {
            "value": False,
            "why": "Not first-pass critical unless setup already exists cleanly."
        },
        "vacuum_wall_coupling_notes": (
            "Keep minimal on pass 1 unless needed by your chosen JOREK example/base case."
        ),
    },
    "recommended_postprocessing_stance": {
        "elm_crash_amplitude": {
            "status": "required",
            "extraction_method": "detect_crash_events_from_time_trace_then_measure_amplitude_drop",
            "notes": "Use the same event-detection rule across A/B/C/D."
        },
        "elm_energy_loss_per_event": {
            "status": "required",
            "extraction_method": "integrate_energy_change_across_each_detected_event",
            "notes": "Use same integration window logic for all cases."
        },
        "peak_divertor_heat_flux": {
            "status": "required",
            "extraction_method": "max_target_heat_flux_over_time_and_over_detected_events",
            "notes": "Must specify which target/divertor surface and normalization."
        },
        "wetted_area": {
            "status": "required",
            "extraction_method": "area_above_defined_heat_flux_threshold_on_target",
            "notes": "Threshold must be identical across all cases."
        },
        "elm_frequency": {
            "status": "required",
            "extraction_method": "count_detected_events_per_unit_time",
            "notes": "Depends on using the same event detector everywhere."
        },
        "stability_window_shift": {
            "status": "required",
            "extraction_method": (
                "compare onset/severity behavior between baseline and controlled cases "
                "under same drive convention"
            ),
            "notes": "Can be qualitative on pass 1 if fully quantitative threshold scan is not yet feasible."
        },
    },
    "case_specific_notes": {},
    "remaining_decisions": [
        "Accept synthetic equilibrium/profile source for first synthetic campaign, or replace with real source",
        "Choose concrete SOL/divertor treatment from actual JOREK example/base case",
        "Choose actual boundary condition implementation compatible with chosen JOREK setup",
        "Define exact diagnostics/variables used for event detection",
        "Define exact target surface and normalization for peak divertor heat flux",
        "Define wetted-area threshold convention",
    ],
}

for case in run_plan["cases"]:
    name = case["case_name"]
    sheet["case_specific_notes"][name] = {
        "purpose": case["purpose"],
        "boundary_intent": (
            "Use same boundary/divertor treatment across all four cases unless there is a compelling reason not to."
        ),
        "postprocessing_intent": (
            "Use same event detector, same heat-flux extraction location, same wetted-area threshold, same time normalization."
        ),
        "launch_ready": False,
        "case_blockers": [
            "Need explicit equilibrium/profile acceptance",
            "Need explicit boundary/divertor implementation choice",
            "Need explicit extraction script or method",
        ],
    }

with out_json.open("w", encoding="utf-8") as f:
    json.dump(sheet, f, indent=2)

md = []
md.append("# JOREK Boundary/Divertor and Postprocessing Sheet")
md.append("")
md.append("## Frozen reference")
for k, v in sheet["frozen_reference"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Recommended boundary stance")
for k, v in sheet["recommended_boundary_stance"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Recommended postprocessing stance")
for k, v in sheet["recommended_postprocessing_stance"].items():
    md.append(f"- {k}: {v}")
md.append("")
md.append("## Case-specific notes")
for case_name, info in sheet["case_specific_notes"].items():
    md.append(f"### {case_name}")
    for k, v in info.items():
        md.append(f"- {k}: {v}")
    md.append("")
md.append("## Remaining decisions")
for item in sheet["remaining_decisions"]:
    md.append(f"- {item}")
md.append("")

out_md.write_text("\n".join(md), encoding="utf-8")

checklist = """# JOREK Boundary/Divertor and Postprocessing Checklist

## Boundary / divertor
- [ ] boundary strategy chosen
- [ ] SOL treatment chosen
- [ ] divertor representation chosen
- [ ] target surface for heat-flux extraction chosen
- [ ] sheath BC accepted or rejected explicitly
- [ ] resistive wall choice accepted or rejected explicitly

## Event detector
- [ ] event detector variable chosen
- [ ] event detector threshold chosen
- [ ] same detector used across A/B/C/D

## Output extraction
- [ ] elm_crash_amplitude method written
- [ ] elm_energy_loss_per_event method written
- [ ] peak_divertor_heat_flux method written
- [ ] wetted_area threshold written
- [ ] elm_frequency method written
- [ ] stability_window_shift comparison rule written

## Consistency rules
- [ ] same normalization across all cases
- [ ] same target surface across all cases
- [ ] same event window logic across all cases
- [ ] same wetted-area threshold across all cases

## Go / no-go
- [ ] enough chosen to draft postprocessing scripts
- [ ] enough chosen to compare A/B/C/D fairly
"""

out_checklist.write_text(checklist, encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
print(" -", out_checklist)
