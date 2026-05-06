import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
RUNS = ROOT / "jorek_campaign_package" / "runs"
OUT = ROOT / "jorek_campaign_package"

CASE_NAMES = [
    "case_A_baseline_low_control",
    "case_B_high_flow",
    "case_C_stabilized_surrogate",
    "case_D_combined",
]

def load_case(name: str):
    path = RUNS / name / "case_template.json"
    if not path.exists():
        raise SystemExit(f"Missing case file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            flatten(key, v, out)
    elif isinstance(obj, list):
        out[prefix] = obj
    else:
        out[prefix] = obj

cases = {name: load_case(name) for name in CASE_NAMES}
base = cases["case_A_baseline_low_control"]

sections_to_compare = [
    "case_controls",
    "physics_switches",
    "numerics",
    "boundary_and_divertor",
    "diagnostics",
]

base_flat = {}
for sec in sections_to_compare:
    flatten(sec, base.get(sec, {}), base_flat)

report = {
    "baseline_case": "case_A_baseline_low_control",
    "sections_compared": sections_to_compare,
    "diffs": {},
    "summary": {},
}

for name, case in cases.items():
    if name == "case_A_baseline_low_control":
        continue

    case_flat = {}
    for sec in sections_to_compare:
        flatten(sec, case.get(sec, {}), case_flat)

    diffs = []
    all_keys = sorted(set(base_flat) | set(case_flat))
    for key in all_keys:
        a = base_flat.get(key, "<missing>")
        b = case_flat.get(key, "<missing>")
        if a != b:
            diffs.append({
                "field": key,
                "baseline": a,
                "candidate": b,
            })

    report["diffs"][name] = diffs
    report["summary"][name] = {
        "num_differences": len(diffs),
        "intended_focus": (
            "flow/shear delta only" if name == "case_B_high_flow" else
            "stabilization-surrogate delta only" if name == "case_C_stabilized_surrogate" else
            "combined flow/shear + stabilization-surrogate delta"
        ),
    }

json_path = OUT / "jorek_case_diff_report.json"
md_path = OUT / "jorek_case_diff_report.md"

json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

md = []
md.append("# JOREK Case Diff Report")
md.append("")
md.append(f"- baseline_case: {report['baseline_case']}")
md.append(f"- sections_compared: {', '.join(report['sections_compared'])}")
md.append("")

for name in CASE_NAMES[1:]:
    md.append(f"## {name}")
    md.append(f"- intended_focus: {report['summary'][name]['intended_focus']}")
    md.append(f"- num_differences: {report['summary'][name]['num_differences']}")
    md.append("")
    for d in report["diffs"][name]:
        md.append(f"### {d['field']}")
        md.append(f"- baseline: {d['baseline']}")
        md.append(f"- candidate: {d['candidate']}")
        md.append("")
        
md_path.write_text("\n".join(md), encoding="utf-8")

print("Wrote:")
print(" -", json_path)
print(" -", md_path)
