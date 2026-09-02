#!/usr/bin/env python3
"""Frozen RF-equivalent current-profile audit for native M3D-C1.

This is not an RF wave simulation. It audits the existing native current-drive
and center/shoulder redistribution operators as controlled proxies for a
deposited RF current profile. Transport, equilibrium, mesh, and solver physics
remain unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
SRC = Path("/home/ubuntu/M3DC1-official")
BUILD = SRC / "build-ubuntu-2d"
EXE = BUILD / "unstructured/m3dc1_2d"
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
OUT = REPO / "validation_runs/m3dc1_tct_rf_profile"
RUN_ROOT = Path("/tmp/m3dc1_tct_rf_profile_runs")

DT = 0.01
NTIMEMAX = 40
NTIMEPR = 1
T_END = 0.40
R0 = 10.0
Z0 = 1.0
ZERO_TOL = 1e-12
WIDTH_NOISE_PCT = 0.02
JPK_TOL_PCT = 0.10

# Frozen matrix: signs, deposition width, timing, and one explicit shoulder
# shaping case. No physics coefficient is varied.
CASES = [
    {"name": "rf_counter_pulse_w050", "source": 1, "amp": -0.02, "width": 0.50, "t_on": 0.00, "t_off": 0.05},
    {"name": "rf_co_pulse_w050", "source": 1, "amp": 0.02, "width": 0.50, "t_on": 0.00, "t_off": 0.05},
    {"name": "rf_counter_pulse_w025", "source": 1, "amp": -0.02, "width": 0.25, "t_on": 0.00, "t_off": 0.05},
    {"name": "rf_counter_prebias_w050", "source": 1, "amp": -0.01, "width": 0.50, "t_on": 0.00, "t_off": 0.25},
    {"name": "rf_counter_shoulder_pulse", "source": 4, "amp": -0.02, "width": 0.25,
     "shoulder_width": 0.25, "shoulder_delta": 0.56, "t_on": 0.00, "t_off": 0.05},
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_mesh_assets(d: Path) -> None:
    for item in pta.COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)


def launch_script(d: Path) -> None:
    text = f'''#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "{d}"
set +e
timeout 1200s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\\n' "$rc" > run_status.txt
exit "$rc"
'''
    (d / "launch_command.sh").write_text(text)
    (d / "launch_command.sh").chmod(0o755)


def prepare(name: str, *, source: int, amp: float, width: float = 0.50,
            shoulder_width: float = 0.25, shoulder_delta: float = 0.56,
            t_on: float = 0.0, t_off: float = 0.0) -> Path:
    d = RUN_ROOT / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    copy_mesh_assets(d)
    text = (BASE / "C1input").read_text()
    updates = {
        "dt": f"{DT:.10g}",
        "ntimemax": str(NTIMEMAX),
        "ntimepr": str(NTIMEPR),
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": str(source),
        "J_0cd": f"{amp:.10g}",
        "R_0cd": f"{R0:.10g}",
        "Z_0cd": f"{Z0:.10g}",
        "W_cd": f"{width:.10g}",
        "W_cd_shoulder": f"{shoulder_width:.10g}",
        "delta_cd": f"{shoulder_delta:.10g}",
        "cd_t_on": f"{t_on:.10g}",
        "cd_t_ramp": "0.0",
        "cd_t_off": f"{t_off:.10g}",
    }
    for key, value in updates.items():
        text = pta.replace_or_add(text, key, value)
    (d / "C1input").write_text(text)
    launch_script(d)
    return d


def prepare_baseline() -> Path:
    d = RUN_ROOT / "baseline"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    copy_mesh_assets(d)
    text = (BASE / "C1input").read_text()
    for key, value in {
        "dt": f"{DT:.10g}", "ntimemax": str(NTIMEMAX),
        "ntimepr": str(NTIMEPR), "imag_control": "0",
        "mag_ctrl_amp": "0.0", "icd_source": "0", "J_0cd": "0.0",
    }.items():
        text = pta.replace_or_add(text, key, value)
    (d / "C1input").write_text(text)
    launch_script(d)
    return d


def execute(d: Path) -> None:
    t0 = time.time()
    p = pta.sh(["bash", "launch_command.sh"], cwd=d)
    (d / "wrapper_stdout.log").write_text(p.stdout)
    (d / "elapsed_seconds.txt").write_text(f"{time.time()-t0:.6f}\n")
    if p.returncode:
        raise RuntimeError(f"{d.name} failed rc={p.returncode}\n{p.stdout[-4000:]}")


def pct(control: float, baseline: float) -> float:
    return 100.0 * (control / baseline - 1.0) if abs(baseline) > 1e-300 else math.nan


def trapz(rows: list[dict[str, float]], key: str, t0: float, t1: float) -> float:
    selected = [r for r in rows if t0 <= r["time"] <= t1]
    return sum(0.5 * (a[key] + b[key]) * (b["time"] - a["time"])
               for a, b in zip(selected, selected[1:]))


def compare(spec: dict, base: list[dict[str, float]], control: list[dict[str, float]]) -> tuple[dict, list[dict]]:
    if len(base) != len(control):
        raise RuntimeError(f"{spec['name']}: unequal output lengths {len(base)} != {len(control)}")
    deltas = []
    for b, c in zip(base, control):
        deltas.append({
            "time": c["time"],
            "width_gain_pct": pct(c["W_sheet"], b["W_sheet"]),
            "Jpk_change_pct": pct(c["Jpk"], b["Jpk"]),
            "high_J_change_pct": pct(c["Jint_high"], b["Jint_high"]),
            "center_change_pct": pct(c["center_abs_current"], b["center_abs_current"]),
            "shoulder_change_pct": pct(c["shoulder_abs_current"], b["shoulder_abs_current"]),
            "delta_Reconnected_Flux": c["Reconnected_Flux"] - b["Reconnected_Flux"],
            "delta_reconnection_rate": c["reconnection_rate"] - b["reconnection_rate"],
            "delta_magnetic_energy": c["magnetic_energy"] - b["magnetic_energy"],
        })
    # Impulse response is measured only after the command has ended. This
    # prevents command-on and pre-actuation samples from diluting the gate.
    response = [r for r in deltas if spec["t_off"] < r["time"] <= min(T_END, spec["t_off"] + 0.10)]
    if not response:
        response = [r for r in deltas if r["time"] > spec["t_off"]]
    peak = max(response, key=lambda r: r["width_gain_pct"])
    mean_width = sum(r["width_gain_pct"] for r in response) / len(response)
    mean_jpk = sum(r["Jpk_change_pct"] for r in response) / len(response)
    max_jpk = max(r["Jpk_change_pct"] for r in response)
    high_int_pct = pct(
        trapz(control, "Jint_high", spec["t_off"], min(T_END, spec["t_off"] + 0.10)),
        trapz(base, "Jint_high", spec["t_off"], min(T_END, spec["t_off"] + 0.10)),
    )
    impulse_authority = (
        peak["width_gain_pct"] > WIDTH_NOISE_PCT
        and peak["Jpk_change_pct"] <= JPK_TOL_PCT
        and peak["high_J_change_pct"] <= 0.0
    )
    width_only = peak["width_gain_pct"] > WIDTH_NOISE_PCT
    if impulse_authority:
        classification = "M3DC1_RF_PROFILE_PROXY_IMPULSE_AUTHORITY"
    elif width_only:
        classification = "M3DC1_RF_PROFILE_PROXY_WIDTH_ONLY"
    elif max_jpk > JPK_TOL_PCT:
        classification = "M3DC1_RF_PROFILE_PROXY_J_WORSE"
    else:
        classification = "M3DC1_RF_PROFILE_PROXY_NO_AUTHORITY"
    return {
        "case": spec["name"],
        "source_mode": spec["source"],
        "amp": spec["amp"],
        "width": spec["width"],
        "t_on": spec["t_on"],
        "t_off": spec["t_off"],
        "peak_response_time": peak["time"],
        "response_latency": peak["time"] - spec["t_off"],
        "response_duration_window": min(T_END, spec["t_off"] + 0.10) - spec["t_off"],
        "classification": classification,
        "impulse_authority": impulse_authority,
        "mean_response_width_gain_pct": mean_width,
        "peak_favorable_width_gain_pct": peak["width_gain_pct"],
        "corresponding_Jpk_change_pct": peak["Jpk_change_pct"],
        "corresponding_high_J_change_pct": peak["high_J_change_pct"],
        "mean_response_Jpk_change_pct": mean_jpk,
        "max_response_Jpk_change_pct": max_jpk,
        "integrated_high_J_change_pct": high_int_pct,
        "center_change_at_peak_pct": peak["center_change_pct"],
        "shoulder_change_at_peak_pct": peak["shoulder_change_pct"],
        "delta_Reconnected_Flux_at_peak": peak["delta_Reconnected_Flux"],
        "delta_magnetic_energy_at_peak": peak["delta_magnetic_energy"],
    }, deltas


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # Build only; this audit uses existing native icd_source code and does not
    # install or mutate a new Fortran operator.
    pta.build()
    baseline_dir = prepare_baseline()
    zero_dir = prepare("zero_current_drive", source=1, amp=0.0, t_off=0.05)
    case_dirs = {
        c["name"]: prepare(
            c["name"], source=c["source"], amp=c["amp"], width=c["width"],
            shoulder_width=c.get("shoulder_width", 0.25),
            shoulder_delta=c.get("shoulder_delta", 0.56),
            t_on=c["t_on"], t_off=c["t_off"],
        ) for c in CASES
    }
    for d in [baseline_dir, zero_dir, *case_dirs.values()]:
        print(f"[rf-profile] running {d.name}", flush=True)
        execute(d)

    base = pta.extract(baseline_dir)
    zero = pta.extract(zero_dir)
    max_zero = 0.0
    for b, z in zip(base, zero):
        for key in ("W_sheet", "Jpk", "Jint_high", "Reconnected_Flux", "magnetic_energy"):
            max_zero = max(max_zero, abs(z[key] - b[key]))
    zero_summary = {"max_abs_metric_delta": max_zero, "tolerance": ZERO_TOL, "pass": max_zero <= ZERO_TOL}
    (OUT / "zero_equivalence.json").write_text(json.dumps(zero_summary, indent=2) + "\n")

    summaries = []
    for spec in CASES:
        summary, deltas = compare(spec, base, pta.extract(case_dirs[spec["name"]]))
        summaries.append(summary)
        write_csv(OUT / f"{spec['name']}_deltas.csv", deltas)
        for item in ("C1input", "C1ke", "run_status.txt", "launcher.stderr", "launch_command.sh", "elapsed_seconds.txt"):
            p = case_dirs[spec["name"]] / item
            if p.exists():
                shutil.copy2(p, OUT / f"{spec['name']}_{item}")

    write_csv(OUT / "rf_profile_matrix.csv", summaries)
    best = max((s for s in summaries if s["impulse_authority"]),
               key=lambda s: s["peak_favorable_width_gain_pct"], default=None)
    report = {
        "classification": "M3DC1_RF_PROFILE_PROXY_IMPULSE_AUTHORITY_FOUND" if best else "M3DC1_RF_PROFILE_PROXY_NO_IMPULSE_AUTHORITY_FOUND",
        "zero_equivalence": zero_summary,
        "best_case": best,
        "cases": summaries,
        "claim_boundary": (
            "Native normalized M3D-C1 deposited-current/profile-shaping proxy only. "
            "No RF frequency, wave propagation, absorption, power calibration, "
            "lithium dimensional transfer, or reactor stabilization is implied."
        ),
    }
    (OUT / "rf_profile_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "runtime_provenance.txt").write_text(
        f"repo={REPO}\nsource={SRC}\nbaseline={BASE}\nexecutable={EXE}\n"
        f"executable_sha256={sha256_file(EXE)}\nrun_root={RUN_ROOT}\n"
        f"dt={DT}\nntimemax={NTIMEMAX}\nntimepr={NTIMEPR}\n"
    )
    (OUT / "RF_PROFILE_PROXY_REPORT.md").write_text(
        "# Native M3D-C1 RF-equivalent profile audit\n\n"
        f"Primary classification: {report['classification']}\n\n"
        "The matrix uses the existing icd_source operator as a deposited-current "
        "proxy. It varies only sign, width, timing, and one center/shoulder profile; "
        "all transport, equilibrium, mesh, and solver physics remain frozen.\n\n"
        + "\n".join(
            f"- {s['case']}: {s['classification']}; peak width "
            f"{s['peak_favorable_width_gain_pct']:.6g}%, corresponding Jpk "
            f"{s['corresponding_Jpk_change_pct']:.6g}%, latency "
            f"{s['response_latency']:.6g}."
            for s in summaries
        )
        + "\n\n## Claim boundary\n\n" + report["claim_boundary"] + "\n"
    )
    print(f"[rf-profile] complete: {OUT}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
