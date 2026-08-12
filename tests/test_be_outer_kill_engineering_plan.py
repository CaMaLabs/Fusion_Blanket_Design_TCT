from pathlib import Path
import json
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_be_outer_kill_engineering_openmc.py"


def test_engineering_plan_smoke(tmp_path):
    run_dir = tmp_path / "engineering_plan"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--run-dir",
            str(run_dir),
            "--plan-only",
            "--check",
            "--seeds",
            "104729,130363",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.returncode == 0, proc.stdout

    plan = json.loads((run_dir / "engineering_plan.json").read_text(encoding="utf-8"))
    assert plan["status"] == "ENGINEERING_DEGRADATION_SCREEN_ONLY"
    assert plan["material_order"] == ["Be", "Li2O", "Li2O", "W_Ti_B4C_60_30_10_wt", "Be"]
    assert len(plan["selected_cases"]) == 4

    control = next(case for case in plan["selected_cases"] if case["name"] == "idealized_control")
    nominal = next(case for case in plan["selected_cases"] if case["name"] == "engineering_nominal")

    assert control["structural_fraction"] == 0.0
    assert control["coolant_channel_count"] == 0
    assert control["port_count"] == 0
    assert control["shield_thickness_cm"] == 0.0

    assert nominal["structural_fraction"] > 0.0
    assert nominal["coolant_channel_count"] > 0
    assert nominal["port_count"] > 0
    assert nominal["shield_thickness_cm"] > 0.0
