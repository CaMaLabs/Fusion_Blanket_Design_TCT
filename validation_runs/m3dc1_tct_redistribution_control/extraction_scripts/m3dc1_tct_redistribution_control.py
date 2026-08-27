#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_redistribution_control"
SRC = Path("/home/ubuntu/M3DC1-official")
RUN_ROOT = Path("/home/ubuntu/m3dc1_runs")
BASE = RUN_ROOT / "TCT_MECHANISM_BASELINE"
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
H5DUMP = Path("/home/ubuntu/spack/opt/spack/linux-skylake/hdf5-1.14.6-uoyar6dpmk3uncnm7a5mogs4losjyziw/bin/h5dump")
COLS = ["ntime","time","ekin","gamma_gr","ekinp","ekint","ekin3","emagp","emagt","emag3","etot"]
SCALARS = ["time","Reconnected_Flux","psi0","psi_lcfs","psimin","xmag","zmag","xnull","znull","toroidal_current","toroidal_flux","volume","loop_voltage"]
R_CENTER = 10.0
R_BAND = 0.25
PREV_NATIVE_SCALE = 0.0203083
ACTUATOR = {
    "icd_source": 4,
    "R_0cd": 10.0,
    "Z_0cd": 1.0,
    "W_cd": 0.2805,
    "delta_cd": 0.561,
    "W_cd_shoulder": 0.2805,
    "cd_t_on": 0.05,
    "cd_t_ramp": 0.05,
    "cd_t_off": 0.25,
}
AUTHORITY = [
    ("A1", 1.0, PREV_NATIVE_SCALE),
    ("A2", 4.0, 4.0 * PREV_NATIVE_SCALE),
    ("A3", 8.0, 8.0 * PREV_NATIVE_SCALE),
]


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> str:
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode:
        raise SystemExit(p.stdout)
    return p.stdout


def nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?|[-+]?\.\d+(?:[Ee][-+]?\d+)?", s)]


def h5data(path: Path, dataset: str) -> list[float]:
    text = run([str(H5DUMP), "-y", "-w", "0", "-d", dataset, path])
    m = re.search(r"DATA \{(.*?)\}\s*}\s*}", text, re.S)
    return nums(m.group(1)) if m else []


def h5shape(path: Path, dataset: str) -> tuple[int, ...]:
    text = run([str(H5DUMP), "-H", "-d", dataset, path])
    m = re.search(r"DATASPACE\s+SIMPLE\s+\{\s*\(\s*([0-9, ]+)\)", text)
    return tuple(int(x.strip()) for x in m.group(1).split(",")) if m else ()


def matrix(path: Path, dataset: str) -> list[list[float]]:
    shape = h5shape(path, dataset)
    data = h5data(path, dataset)
    if len(shape) != 2 or len(data) != shape[0] * shape[1]:
        raise RuntimeError(f"bad {path}:{dataset} {shape} {len(data)}")
    return [data[i * shape[1]:(i + 1) * shape[1]] for i in range(shape[0])]


def c1ke(run_dir: Path) -> list[dict[str, float]]:
    rows = []
    for line in (run_dir / "C1ke").read_text().splitlines():
        if line.strip():
            rows.append(dict(zip(COLS, [float(x) for x in line.split()])))
    return rows


def status(run_dir: Path) -> str:
    p = run_dir / "run_status.txt"
    return p.read_text().strip() if p.exists() else "missing"


def centers_weights(run_dir: Path, t: int) -> list[tuple[float, float, float]]:
    elems = matrix(run_dir / f"time_{t:03d}.h5", "/mesh/elements")
    return [(row[4], row[5], max(row[2], 0.0)) for row in elems]


def field(run_dir: Path, t: int, name: str) -> list[float]:
    return [row[0] for row in matrix(run_dir / f"time_{t:03d}.h5", f"/fields/{name}")]


def profile(run_dir: Path, t: int) -> list[dict[str, float]]:
    rows = []
    for (r, z, w), jj, pp in zip(centers_weights(run_dir, t), field(run_dir, t, "jphi"), field(run_dir, t, "psi")):
        if abs(r - R_CENTER) <= R_BAND:
            rows.append({"R": r, "Z": z, "weight": w, "jphi": jj, "abs_jphi": abs(jj), "psi": pp})
    rows.sort(key=lambda x: x["Z"])
    return rows


def weighted(rows: list[dict[str, float]]) -> dict[str, float]:
    absint = sum(r["abs_jphi"] * r["weight"] for r in rows)
    signed = sum(r["jphi"] * r["weight"] for r in rows)
    mean = sum(r["Z"] * r["abs_jphi"] * r["weight"] for r in rows) / max(absint, 1e-300)
    var = sum((r["Z"] - mean) ** 2 * r["abs_jphi"] * r["weight"] for r in rows) / max(absint, 1e-300)
    peak = max(rows, key=lambda r: r["abs_jphi"])
    center = sum(r["abs_jphi"] * r["weight"] for r in rows if abs(r["Z"] - ACTUATOR["Z_0cd"]) <= ACTUATOR["W_cd"])
    shoulder = sum(r["abs_jphi"] * r["weight"] for r in rows if abs(abs(r["Z"] - ACTUATOR["Z_0cd"]) - ACTUATOR["delta_cd"]) <= ACTUATOR["W_cd_shoulder"])
    return {
        "Jpk": peak["abs_jphi"],
        "Jpk_R": peak["R"],
        "Jpk_Z": peak["Z"],
        "Jint_abs": absint,
        "Jint_signed": signed,
        "W_rms": math.sqrt(max(var, 0.0)),
        "W_fwhm_equiv": 2.354820045 * math.sqrt(max(var, 0.0)),
        "current_centroid_Z": mean,
        "center_abs_current": center,
        "shoulder_abs_current": shoulder,
        "center_to_shoulder_ratio": center / max(shoulder, 1e-300),
    }


def source_shape_integrals(run_dir: Path, t: int, amp: float) -> dict[str, float]:
    raw = []
    area = 0.0
    for r, z, w in centers_weights(run_dir, t):
        if abs(r - R_CENTER) <= R_BAND:
            c = math.exp(-((r - ACTUATOR["R_0cd"]) ** 2) / ACTUATOR["W_cd"] ** 2 - ((z - ACTUATOR["Z_0cd"]) ** 2) / ACTUATOR["W_cd"] ** 2)
            s1 = math.exp(-((r - ACTUATOR["R_0cd"]) ** 2) / ACTUATOR["W_cd_shoulder"] ** 2 - ((z - (ACTUATOR["Z_0cd"] - ACTUATOR["delta_cd"])) ** 2) / ACTUATOR["W_cd_shoulder"] ** 2)
            s2 = math.exp(-((r - ACTUATOR["R_0cd"]) ** 2) / ACTUATOR["W_cd_shoulder"] ** 2 - ((z - (ACTUATOR["Z_0cd"] + ACTUATOR["delta_cd"])) ** 2) / ACTUATOR["W_cd_shoulder"] ** 2)
            val = -c + 0.5 * s1 + 0.5 * s2
            raw.append((val, w))
            area += w
    mean = sum(v * w for v, w in raw) / max(area, 1e-300)
    net = amp * sum((v - mean) * w for v, w in raw)
    l1 = abs(amp) * sum(abs(v - mean) * w for v, w in raw)
    return {"diagnostic_net_injected_current": net, "diagnostic_abs_source_current": l1, "diagnostic_net_to_abs_source_ratio": net / max(l1, 1e-300)}


def scalars(run_dir: Path) -> dict[str, list[float]]:
    return {s: h5data(run_dir / "C1.h5", f"/scalars/{s}") for s in SCALARS}


def series(run_dir: Path, amp: float = 0.0) -> list[dict[str, float]]:
    sc = scalars(run_dir)
    rows = []
    for i, k in enumerate(c1ke(run_dir)):
        row = {"ntime": int(k["ntime"]), "time": k["time"], "kinetic_energy": k["ekin"], "magnetic_energy": k["emagp"] + k["emagt"] + k["emag3"], "total_energy": k["etot"]}
        row.update(weighted(profile(run_dir, i)))
        for s, v in sc.items():
            row[s if s != "Reconnected_Flux" else "Reconnected_Flux"] = v[i] if i < len(v) else math.nan
        row.update(source_shape_integrals(run_dir, i, amp))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        dt = b["time"] - a["time"]
        b["dW_dt"] = (b["W_fwhm_equiv"] - a["W_fwhm_equiv"]) / dt if dt else math.nan
        b["dJpk_dt"] = (b["Jpk"] - a["Jpk"]) / dt if dt else math.nan
        b["dReconnected_Flux_dt"] = (b["Reconnected_Flux"] - a["Reconnected_Flux"]) / dt if dt else math.nan
    if rows:
        rows[0]["dW_dt"] = rows[0]["dJpk_dt"] = rows[0]["dReconnected_Flux_dt"] = math.nan
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def extrema(rows: list[dict[str, float]]) -> dict[str, float]:
    post = rows[1:] or rows
    min_dw = min((r for r in post if math.isfinite(r["dW_dt"])), key=lambda r: r["dW_dt"])
    max_dj = max((r for r in post if math.isfinite(r["dJpk_dt"])), key=lambda r: r["dJpk_dt"])
    peak_j = max(rows, key=lambda r: r["Jpk"])
    finite_rf = [r for r in post if math.isfinite(r["dReconnected_Flux_dt"])]
    peak_rf = max(finite_rf, key=lambda r: abs(r["dReconnected_Flux_dt"])) if finite_rf else rows[0]
    return {
        "rapid_narrowing_onset_time": min_dw["time"],
        "maximum_narrowing_rate_time": min_dw["time"],
        "maximum_narrowing_rate": min_dw["dW_dt"],
        "rapid_current_growth_time": max_dj["time"],
        "maximum_current_growth_rate": max_dj["dJpk_dt"],
        "uncontrolled_peak_current_time": peak_j["time"],
        "uncontrolled_peak_Jpk": peak_j["Jpk"],
        "topology_reconnection_onset_time": peak_rf["time"],
        "peak_abs_reconnection_rate_proxy": abs(peak_rf["dReconnected_Flux_dt"]),
    }


def replace_or_add(text: str, key: str, value: str) -> str:
    pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if pat.search(text):
        return pat.sub(rf"\g<1>{value}", text)
    return text.replace("\n /\n", f"\n {key} = {value}\n /\n")


def prepare_run(run_dir: Path, name: str, amp: float, t_on: float | None = None, t_off: float | None = None) -> None:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    for item in ["circle-0.10-0.0-0.0-1K0.smb", "circle-0.10-0.0-0.0.txt", "part0.smb", "part.smb"]:
        src = BASE / item
        if src.is_symlink():
            (run_dir / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, run_dir / item)
    text = (BASE / "C1input").read_text()
    for key, val in ACTUATOR.items():
        if key == "cd_t_on" and t_on is not None:
            val = t_on
        if key == "cd_t_off" and t_off is not None:
            val = t_off
        text = replace_or_add(text, key, str(val))
    text = replace_or_add(text, "J_0cd", f"{amp:.10g}")
    (run_dir / "C1input").write_text(text)
    launch = f"""#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "{run_dir}"
timeout 300s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\\n" "$?" > run_status.txt
"""
    (run_dir / "launch_command.sh").write_text(launch)
    (run_dir / "launch_command.sh").chmod(0o755)
    run(["sha256sum", "C1input", "part0.smb", "circle-0.10-0.0-0.0.txt"], cwd=run_dir, check=False)


def launch(run_dir: Path) -> None:
    run(["bash", "launch_command.sh"], cwd=run_dir, check=True)


def copy_compact(run_dir: Path, prefix: str) -> None:
    for f in ["C1input", "C1ke", "run_status.txt", "launcher.stderr", "launch_command.sh"]:
        if (run_dir / f).exists():
            shutil.copy2(run_dir / f, OUT / f"{prefix}_{f}")
    if (run_dir / "C1stdout").exists():
        keep = [ln for ln in (run_dir / "C1stdout").read_text(errors="replace").splitlines() if re.search(r"WARNING|Warning|ERROR|Error|mesh entity counts|magnetic axis|X-point|Poloidal flux|Total energy|Toroidal current|Toroidal flux|Volume|TIME STEP|Stopped at|Done time loop", ln)]
        (OUT / f"compact_{prefix}_stdout.log").write_text("\n".join(keep) + "\n")


def summarize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    natural = series(BASE, 0.0)
    write_csv(OUT / "natural_sheet_dynamics.csv", natural)
    natural_summary = extrema(natural)
    (OUT / "natural_sheet_dynamics_summary.json").write_text(json.dumps(natural_summary, indent=2) + "\n")
    zero_dir = RUN_ROOT / "TCT_REDIS_ZERO"
    if (zero_dir / "C1ke").exists():
        zero = series(zero_dir, 0.0)
        write_csv(OUT / "zero_controller_timeseries.csv", zero)
        copy_compact(zero_dir, "zero")
        fields = ["Jpk", "Jint_abs", "Jint_signed", "W_fwhm_equiv", "Reconnected_Flux", "magnetic_energy", "kinetic_energy", "total_energy"]
        diffs = {f: max(abs(a[f] - b[f]) for a, b in zip(natural, zero)) for f in fields}
        c1ke_base = c1ke(BASE)
        c1ke_zero = c1ke(zero_dir)
        c1ke_diff = max(abs(a[k] - b[k]) for a, b in zip(c1ke_base, c1ke_zero) for k in COLS)
        eq = {
            "status": "PASS" if status(zero_dir) == "return_code=0" and c1ke_diff == 0.0 and max(diffs.values()) == 0.0 else "FAIL",
            "baseline_run": str(BASE),
            "zero_controller_run": str(zero_dir),
            "controller_path": "icd_source=4 with J_0cd=0",
            "run_status": status(zero_dir),
            "c1ke_max_abs_difference": c1ke_diff,
            "timeseries_max_abs_differences": diffs,
        }
        (OUT / "controller_zero_equivalence.json").write_text(json.dumps(eq, indent=2) + "\n")
    rows = []
    for name, factor, amp in AUTHORITY:
        run_dir = RUN_ROOT / f"TCT_REDIS_AUTH_{name}"
        if not (run_dir / "C1ke").exists():
            continue
        s = series(run_dir, amp)
        write_csv(OUT / f"{name.lower()}_timeseries.csv", s)
        copy_compact(run_dir, name.lower())
        active = [r for r in s if ACTUATOR["cd_t_on"] <= r["time"] <= ACTUATOR["cd_t_off"]]
        base_active = [r for r in natural if ACTUATOR["cd_t_on"] <= r["time"] <= ACTUATOR["cd_t_off"]]
        rows.append({
            "case": name,
            "factor_vs_previous_native_scale": factor,
            "J_0cd": amp,
            "run_status": status(run_dir),
            "min_dW_dt_active": min(r["dW_dt"] for r in active if math.isfinite(r["dW_dt"])),
            "baseline_min_dW_dt_active": min(r["dW_dt"] for r in base_active if math.isfinite(r["dW_dt"])),
            "peak_Jpk_active": max(r["Jpk"] for r in active),
            "baseline_peak_Jpk_active": max(r["Jpk"] for r in base_active),
            "peak_Jpk_change_pct_active": 100.0 * (max(r["Jpk"] for r in active) - max(r["Jpk"] for r in base_active)) / max(r["Jpk"] for r in base_active),
            "mean_width_gain_pct_active": 100.0 * (sum(r["W_fwhm_equiv"] for r in active) / len(active) - sum(r["W_fwhm_equiv"] for r in base_active) / len(base_active)) / (sum(r["W_fwhm_equiv"] for r in base_active) / len(base_active)),
            "max_abs_net_source_ratio": max(abs(r["diagnostic_net_to_abs_source_ratio"]) for r in active),
            "final_magnetic_energy_change_pct": 100.0 * (s[-1]["magnetic_energy"] - natural[-1]["magnetic_energy"]) / natural[-1]["magnetic_energy"],
            "final_kinetic_energy_change_pct": 100.0 * (s[-1]["kinetic_energy"] - natural[-1]["kinetic_energy"]) / max(natural[-1]["kinetic_energy"], 1e-300),
            "final_reconnected_flux_change_pct": 100.0 * (s[-1]["Reconnected_Flux"] - natural[-1]["Reconnected_Flux"]) / natural[-1]["Reconnected_Flux"],
        })
    if rows:
        write_csv(OUT / "actuator_authority_matrix.csv", rows)
        min_capable = next((r for r in rows if r["min_dW_dt_active"] > r["baseline_min_dW_dt_active"]), None)
        summary = {
            "classification": "M3DC1_TCT_CONTROL_AUTHORITY_INSUFFICIENT" if min_capable is None else "M3DC1_TCT_NATIVE_REDISTRIBUTION_AUTHORITY_IDENTIFIED",
            "predeclared_cases": rows,
            "minimum_authority_opposing_narrowing": min_capable["case"] if min_capable else None,
            "interpretation": "actuator/controller mapping remains the bottleneck; do not falsify current-sheet mechanism" if min_capable is None else "candidate amplitudes are available for frozen controller-state selection",
        }
        (OUT / "actuator_authority_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    patch = run(["git", "diff", "--", "unstructured/M3Dmodules.f90", "unstructured/input.f90", "unstructured/transport.f90"], cwd=SRC)
    (OUT / "native_redistribution_source_patch.diff").write_text(patch)


def write_docs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "actuator_authority_plan.md").write_text(f"""# M3D-C1 Native Redistribution Authority Plan

Actuator mode: `icd_source = 4`, through native `cd_func()` current-drive source path.

Spatial form:

`S = A * (-G_center + 0.5 G_lower_shoulder + 0.5 G_upper_shoulder)`

The source is numerically mean-subtracted over plasma quadrature points before projection, so the applied redistribution is net-current-neutral on the same native source path.

Frozen geometry:

- `R_0cd = {ACTUATOR['R_0cd']}`
- `Z_0cd = {ACTUATOR['Z_0cd']}`
- `W_cd = {ACTUATOR['W_cd']}`
- `delta_cd = {ACTUATOR['delta_cd']}`
- `W_cd_shoulder = {ACTUATOR['W_cd_shoulder']}`
- active window: `{ACTUATOR['cd_t_on']} <= t < {ACTUATOR['cd_t_off']}`, ramp `{ACTUATOR['cd_t_ramp']}`

Frozen amplitudes before execution:

- A1: `J_0cd = {AUTHORITY[0][2]:.7g}` = 1x previous native local source scale
- A2: `J_0cd = {AUTHORITY[1][2]:.7g}` = 4x previous native local source scale
- A3: `J_0cd = {AUTHORITY[2][2]:.7g}` = 8x previous native local source scale

Purpose: identify whether native redistribution can oppose the measured natural sheet-narrowing rate, not tune reconnection output.
""")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 1 or sys.argv[1] == "summarize":
        summarize()
        write_docs()
    elif sys.argv[1] == "prepare":
        prepare_run(RUN_ROOT / "TCT_REDIS_ZERO", "zero", 0.0)
        for name, _, amp in AUTHORITY:
            prepare_run(RUN_ROOT / f"TCT_REDIS_AUTH_{name}", name, amp)
        write_docs()
    elif sys.argv[1] == "run-zero":
        launch(RUN_ROOT / "TCT_REDIS_ZERO")
    elif sys.argv[1] == "run-authority":
        for name, _, _ in AUTHORITY:
            launch(RUN_ROOT / f"TCT_REDIS_AUTH_{name}")
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")


if __name__ == "__main__":
    main()
