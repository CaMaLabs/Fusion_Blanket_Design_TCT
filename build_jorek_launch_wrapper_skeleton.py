import json
from pathlib import Path

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_json = PKG / "jorek_run_plan_merged.json"
skeletons_dir = PKG / "jorek_input_deck_skeletons"

out_py = PKG / "jorek_launch_wrapper.py"
out_json = PKG / "jorek_launch_cases.json"
out_md = PKG / "jorek_launch_README.md"

required = [run_plan_json, skeletons_dir]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required files:\n" + "\n".join(missing))

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

cases = []
for case in run_plan["cases"]:
    case_name = case["case_name"]
    template_json = skeletons_dir / f"{case_name}.json"
    template_md = skeletons_dir / f"{case_name}.md"

    cases.append({
        "case_name": case_name,
        "template_json": str(template_json),
        "template_md": str(template_md),
        "run_dir": str(PKG / "runs" / case_name),
        "status": "not_staged",
    })

wrapper_py = r'''#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def stage_case(case: dict, dry_run: bool = False):
    run_dir = Path(case["run_dir"])
    ensure_dir(run_dir)

    src_json = Path(case["template_json"])
    src_md = Path(case["template_md"])

    staged_json = run_dir / "case_template.json"
    staged_md = run_dir / "case_template.md"
    staged_notes = run_dir / "LAUNCH_BLOCKERS.txt"
    staged_log = run_dir / "launch.log"

    actions = [
        f"mkdir -p {run_dir}",
        f"copy {src_json} -> {staged_json}",
        f"copy {src_md} -> {staged_md}",
        f"write {staged_notes}",
        f"touch {staged_log}",
    ]

    if dry_run:
        return actions

    shutil.copy2(src_json, staged_json)
    shutil.copy2(src_md, staged_md)

    blockers = """This run directory is STAGED ONLY.

Not launch-ready yet.

Replace placeholders in case_template.json / case_template.md with:
- actual equilibrium file
- actual profile inputs
- actual JOREK syntax / namelist structure
- actual boundary/divertor implementation
- actual diagnostics / extraction variables

Then wire in the real JOREK executable/launcher.
"""
    staged_notes.write_text(blockers, encoding="utf-8")
    staged_log.touch()

    return actions


def main():
    parser = argparse.ArgumentParser(description="Stage JOREK run directories from case skeletons.")
    parser.add_argument("--cases-json", required=True, help="Path to jorek_launch_cases.json")
    parser.add_argument("--case", default="all", help="Specific case name or 'all'")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without staging")
    args = parser.parse_args()

    cases_json = Path(args.cases_json)
    with cases_json.open("r", encoding="utf-8") as f:
        cases = json.load(f)

    selected = cases if args.case == "all" else [c for c in cases if c["case_name"] == args.case]

    if not selected:
        raise SystemExit(f"No matching cases found for: {args.case}")

    for case in selected:
        print(f"=== staging {case['case_name']} ===")
        actions = stage_case(case, dry_run=args.dry_run)
        for action in actions:
            print(action)


if __name__ == "__main__":
    main()
'''

readme = """# JOREK Launch Wrapper Skeleton

This is the final scaffolding layer.

What it does:
- stages one run directory per case
- copies the per-case skeleton files into the run directory
- creates a LAUNCH_BLOCKERS.txt reminder
- creates an empty launch.log

What it does NOT do:
- launch JOREK
- generate real JOREK namelist syntax
- fill actual equilibrium/profile files
- connect to a scheduler
- parse outputs

## Files
- jorek_launch_wrapper.py
- jorek_launch_cases.json

## Example dry run
python jorek_launch_wrapper.py --cases-json jorek_launch_cases.json --dry-run

## Example stage all
python jorek_launch_wrapper.py --cases-json jorek_launch_cases.json

## Example stage one case
python jorek_launch_wrapper.py --cases-json jorek_launch_cases.json --case case_A_baseline_low_control
"""

out_py.write_text(wrapper_py, encoding="utf-8")
out_json.write_text(json.dumps(cases, indent=2), encoding="utf-8")
out_md.write_text(readme, encoding="utf-8")

print("Wrote:")
print(" -", out_py)
print(" -", out_json)
print(" -", out_md)
