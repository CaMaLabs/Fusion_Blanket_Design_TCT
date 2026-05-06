import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

final_json = PKG / "jorek_run_plan_final.json"
out_json = PKG / "jorek_run_plan_anchored.json"
out_md = PKG / "jorek_run_plan_anchored.md"

if not final_json.exists():
    raise SystemExit(f"Missing required file: {final_json}")

with final_json.open("r", encoding="utf-8") as f:
    plan = json.load(f)

anchor = {
    "primary": "PRL_2015_multi_ELM_cycle",
    "secondary": "RMP_multi_ELM_mitigation_case",
    "heat_flux_anchor": "JET_ILW_JPN83334_wall_aligned_grid_case",
}

role_map = {
    "case_A_baseline_low_control": "published-anchor baseline reference case",
    "case_B_high_flow": "published-anchor high-flow delta case",
    "case_C_stabilized_surrogate": "published-anchor stabilization-surrogate delta case",
    "case_D_combined": "published-anchor combined delta case",
}

intent_map = {
    "case_A_baseline_low_control": [
        "Baseline reference for all later comparisons.",
        "Keep this case boring and stable as the anchor.",
    ],
    "case_B_high_flow": [
        "Vary flow/shear terms relative to case_A.",
        "Do not change extraction conventions or unrelated physics.",
    ],
    "case_C_stabilized_surrogate": [
        "Vary stabilization-surrogate/profile-control terms relative to case_A.",
        "Do not add the high-flow delta here.",
    ],
    "case_D_combined": [
        "Combine the high-flow delta and stabilization-surrogate delta.",
        "Expected best-performing comparison case if the concept survives translation.",
    ],
}

for case in plan["cases"]:
    name = case["case_name"]
    case["published_anchor_primary"] = anchor["primary"]
    case["published_anchor_secondary"] = anchor["secondary"]
    case["published_anchor_heat_flux"] = anchor["heat_flux_anchor"]
    case["published_anchor_role"] = role_map.get(name, "published-anchor comparison case")
    case["published_anchor_intent"] = intent_map.get(name, [])

    note = (
        f"Anchored to published JOREK literature baseline family. "
        f"Role: {case['published_anchor_role']}."
    )
    existing = str(case.get("case_specific_override_notes", "")).strip()
    case["case_specific_override_notes"] = f"{existing} {note}".strip()

plan["campaign_anchor_family"] = anchor
plan["campaign_status"] = "published_anchor_family_aligned"

with out_json.open("w", encoding="utf-8") as f:
    json.dump(plan, f, indent=2)

md = []
md.append("# JOREK Run Plan Anchored")
md.append("")
md.append("## Campaign anchor family")
md.append(f"- primary: {anchor['primary']}")
md.append(f"- secondary: {anchor['secondary']}")
md.append(f"- heat_flux_anchor: {anchor['heat_flux_anchor']}")
md.append("")
for case in plan["cases"]:
    md.append(f"## {case['case_name']}")
    md.append(f"- purpose: {case.get('purpose', '')}")
    md.append(f"- published_anchor_role: {case.get('published_anchor_role', '')}")
    md.append("- published_anchor_intent:")
    for item in case.get("published_anchor_intent", []):
        md.append(f"  - {item}")
    md.append(f"- toroidal_flow_profile: {case.get('toroidal_flow_profile', '')}")
    md.append(f"- poloidal_flow_profile: {case.get('poloidal_flow_profile', '')}")
    md.append(f"- pedestal_pressure_gradient_setting: {case.get('pedestal_pressure_gradient_setting', '')}")
    md.append(f"- edge_current_gradient_setting: {case.get('edge_current_gradient_setting', '')}")
    md.append(f"- tct_surrogate_definition: {case.get('tct_surrogate_definition', '')}")
    md.append("")

out_md.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", out_json)
print(" -", out_md)
