#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_gem"
SRC = Path("/home/ubuntu/M3DC1-official")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_GEM_CIRCLE_BASELINE_AXISFIX")
REPEAT = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_GEM_CIRCLE_BASELINE_REPEAT")
CTRL = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_GEM_CIRCLE_CONTROLLED_EPS0856636")
REV = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_GEM_CIRCLE_FALSIFICATION_EPS_NEG0856636")
RMP_BAD_CHECKED = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_NONLIN_BASELINE_3D_CLEAN")
RMP_BAD_SPLIT = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_NONLIN_REGENERATED_16PART")
H5DUMP = Path("/home/ubuntu/spack/opt/spack/linux-skylake/hdf5-1.14.6-uoyar6dpmk3uncnm7a5mogs4losjyziw/bin/h5dump")
COLS = ["ntime", "time", "ekin", "gamma_gr", "ekinp", "ekint", "ekin3", "emagp", "emagt", "emag3", "etot"]


def run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def c1ke(path: Path) -> list[dict[str, float]]:
    rows = []
    with (path / "C1ke").open() as f:
        for line in f:
            if line.strip():
                rows.append(dict(zip(COLS, [float(x) for x in line.split()])))
    return rows


def stdout_vals(path: Path) -> dict[str, list[float] | list[str] | bool]:
    text = (path / "C1stdout").read_text(errors="replace")
    out: dict[str, list[float] | list[str] | bool] = {}
    pats = {
        "volume": r"Volume =\s*([-+0-9.Ee]+)",
        "toroidal_current": r"Toroidal current =\s*([-+0-9.Ee]+)",
        "toroidal_flux": r"Toroidal flux =\s*([-+0-9.Ee]+)",
        "total_energy": r"Total energy =\s*([-+0-9.Ee]+)",
        "mesh_counts": r"mesh entity counts: v\s+(\d+) e\s+(\d+) f\s+(\d+) r\s+(\d+)",
    }
    for key, pat in pats.items():
        matches = list(re.finditer(pat, text))
        if key == "mesh_counts" and matches:
            out[key] = [int(x) for x in matches[0].groups()]
        elif matches:
            out[key] = [float(m.group(1)) for m in matches]
    out["warnings"] = re.findall(r"WARNING:.*|Warning:.*", text)
    out["axis_not_found_count"] = len(re.findall(r"no magnetic axis found", text))
    out["xpoint_not_found_count"] = len(re.findall(r"X-point 1 NOT found", text))
    out["xpoint_found_count"] = len(re.findall(r"X-point 1 found", text))
    out["nan_inf_present"] = bool(re.search(r"(?<![A-Za-z])(?:NaN|Inf)(?![A-Za-z])", text, re.I))
    return out


def h5_scalar(path: Path, dataset: str) -> list[float]:
    text = run([str(H5DUMP), "-y", "-w", "0", "-d", dataset, str(path / "C1.h5")])
    block = re.search(r"DATA \{(.*?)\}", text, re.S)
    if not block:
        return []
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?", block.group(1))]


def status(path: Path) -> str:
    p = path / "run_status.txt"
    return p.read_text().strip() if p.exists() else "missing"


def read_eps(path: Path) -> float | None:
    m = re.search(r"^\s*eps\s*=\s*([-+0-9.Ee]+)", (path / "C1input").read_text(), re.M)
    return float(m.group(1)) if m else None


def pct(new: float, old: float) -> float | None:
    return None if old == 0 else 100.0 * (new - old) / old


def gate(path: Path, repeat_path: Path | None = None, compare_initial_to: Path | None = None) -> dict:
    rows = c1ke(path)
    vals = stdout_vals(path)
    t0 = rows[0]
    mag0 = t0["emagp"] + t0["emagt"] + t0["emag3"]
    volume0 = vals.get("volume", [math.nan])[0]
    current0 = vals.get("toroidal_current", [math.nan])[0]
    flux0 = vals.get("toroidal_flux", [math.nan])[0]
    finite = {
        "volume": math.isfinite(volume0),
        "magnetic_energy": math.isfinite(mag0),
        "kinetic_energy": math.isfinite(t0["ekin"]),
        "current": math.isfinite(current0),
        "flux": math.isfinite(flux0),
    }
    repeat = {"status": "not_requested"}
    if repeat_path:
        rr = c1ke(repeat_path)
        rvals = stdout_vals(repeat_path)
        repeat = {
            "status": "PASS" if status(repeat_path) == "return_code=0" and max(abs(a[k] - b[k]) for a, b in zip(rows, rr) for k in COLS) == 0.0 else "FAIL",
            "repeat_run": str(repeat_path),
            "run_status": status(repeat_path),
            "c1ke_max_abs_difference": max(abs(a[k] - b[k]) for a, b in zip(rows, rr) for k in COLS),
            "initialization_scalar_abs_differences": {
                "volume": abs(volume0 - rvals["volume"][0]),
                "current": abs(current0 - rvals["toroidal_current"][0]),
                "flux": abs(flux0 - rvals["toroidal_flux"][0]),
            },
        }
    reference = {"available": False}
    if compare_initial_to:
        rr = c1ke(compare_initial_to)
        reference = {
            "available": True,
            "comparison_run": str(compare_initial_to),
            "t0_max_abs_difference": max(abs(t0[k] - rr[0][k]) for k in COLS),
            "note": "Controlled t=0 differs in the intended GEM eps perturbation; mesh/transport/equilibrium settings are otherwise identical.",
        }
    ok = status(path) == "return_code=0" and all(finite.values()) and volume0 > 0 and not vals["nan_inf_present"] and (not repeat_path or repeat["status"] == "PASS")
    return {
        "status": "PASS" if ok else "FAIL",
        "run_dir": str(path),
        "run_status": status(path),
        "eps": read_eps(path),
        "volume": volume0,
        "magnetic_energy": mag0,
        "kinetic_energy": t0["ekin"],
        "current": current0,
        "flux": flux0,
        "finite_checks": finite,
        "mesh_check": {"mesh_counts_v_e_f_r": vals.get("mesh_counts"), "partition_count": 1, "status": "PASS" if vals.get("mesh_counts") else "UNKNOWN"},
        "topology_search_check": {"xpoint_found_count": vals["xpoint_found_count"], "xpoint_not_found_count": vals["xpoint_not_found_count"], "axis_not_found_count": vals["axis_not_found_count"], "status": "WARN_INTERMITTENT" if vals["xpoint_not_found_count"] or vals["axis_not_found_count"] else "PASS"},
        "repeatability": repeat,
        "reference_check": reference,
        "warnings": vals["warnings"],
        "fail_reason": None if ok else "nonfinite/zero-volume/runtime/repeatability failure",
    }


def series(path: Path) -> list[dict[str, float]]:
    rows = c1ke(path)
    vals = stdout_vals(path)
    rf = h5_scalar(path, "/scalars/Reconnected_Flux")
    psi0 = h5_scalar(path, "/scalars/psi0")
    xmag = h5_scalar(path, "/scalars/xmag")
    zmag = h5_scalar(path, "/scalars/zmag")
    xnull = h5_scalar(path, "/scalars/xnull")
    znull = h5_scalar(path, "/scalars/znull")
    out = []
    for i, row in enumerate(rows):
        mag = row["emagp"] + row["emagt"] + row["emag3"]
        out.append({
            "time": row["time"],
            "ntime": int(row["ntime"]),
            "ekin": row["ekin"],
            "magnetic_energy": mag,
            "etot": row["etot"],
            "toroidal_current": vals["toroidal_current"][i],
            "toroidal_flux": vals["toroidal_flux"][i],
            "volume": vals["volume"][i],
            "reconnected_flux": rf[i] if i < len(rf) else math.nan,
            "psi0": psi0[i] if i < len(psi0) else math.nan,
            "xmag": xmag[i] if i < len(xmag) else math.nan,
            "zmag": zmag[i] if i < len(zmag) else math.nan,
            "xnull": xnull[i] if i < len(xnull) else math.nan,
            "znull": znull[i] if i < len(znull) else math.nan,
        })
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def compact(path: Path, name: str) -> None:
    if (path / "C1ke").exists() and (path / "C1stdout").exists(): shutil.copy2(path / "C1ke", OUT / f"{name}_C1ke")
    if (path / "launch_command.sh").exists(): shutil.copy2(path / "launch_command.sh", OUT / f"{name}_launch_command.sh")
    if (path / "input_mesh_hashes.sha256").exists(): shutil.copy2(path / "input_mesh_hashes.sha256", OUT / f"{name}_input_mesh_hashes.sha256")
    if (path / "C1stdout").exists():
        lines = (path / "C1stdout").read_text(errors="replace").splitlines()
        keep = [ln for ln in lines if re.search(r"WARNING|Warning|ERROR|mesh entity counts|magnetic axis|X-point|Poloidal flux|Total energy|Toroidal current|Toroidal flux|Volume|TIME STEP|Stopped at|Done time loop", ln)]
        (OUT / f"compact_{name}_stdout.log").write_text("\n".join(keep) + "\n")
    if (path / "launcher.stderr").exists():
        txt = (path / "launcher.stderr").read_text(errors="replace")
        if txt.strip(): (OUT / f"compact_{name}_stderr.log").write_text(txt)
    if (path / "split_smb.stderr").exists():
        txt = (path / "split_smb.stderr").read_text(errors="replace")
        if txt.strip(): (OUT / f"compact_{name}_split_smb_stderr.log").write_text(txt)
    if (path / "split_smb.stdout").exists():
        txt = (path / "split_smb.stdout").read_text(errors="replace")
        if txt.strip(): (OUT / f"compact_{name}_split_smb_stdout.log").write_text(txt)
    if (path / "C1.h5").exists():
        (OUT / f"{name}_hdf5_structure.txt").write_text(run([str(H5DUMP), "-n", str(path / "C1.h5")]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extraction_scripts").mkdir(exist_ok=True)
    base = series(BASE); ctrl = series(CTRL); rev = series(REV)
    write_csv(OUT / "baseline_timeseries.csv", base)
    pair_rows = []
    for b, c in zip(base, ctrl):
        pair_rows.append({
            "time": b["time"],
            "baseline_current_proxy": abs(b["toroidal_current"]),
            "controlled_current_proxy": abs(c["toroidal_current"]),
            "current_proxy_change_pct": pct(abs(c["toroidal_current"]), abs(b["toroidal_current"])),
            "baseline_magnetic_energy": b["magnetic_energy"],
            "controlled_magnetic_energy": c["magnetic_energy"],
            "magnetic_energy_change_pct": pct(c["magnetic_energy"], b["magnetic_energy"]),
            "baseline_reconnected_flux": b["reconnected_flux"],
            "controlled_reconnected_flux": c["reconnected_flux"],
            "reconnected_flux_change_pct": pct(c["reconnected_flux"], b["reconnected_flux"]),
            "baseline_psi0": b["psi0"],
            "controlled_psi0": c["psi0"],
        })
    write_csv(OUT / "native_pair_timeseries.csv", pair_rows)
    peak_b = max(abs(r["toroidal_current"]) for r in base)
    peak_c = max(abs(r["toroidal_current"]) for r in ctrl)
    int_b = sum(abs(r["toroidal_current"]) for r in base)
    int_c = sum(abs(r["toroidal_current"]) for r in ctrl)
    rf_b = base[-1]["reconnected_flux"]
    rf_c = ctrl[-1]["reconnected_flux"]
    mag_b = base[-1]["magnetic_energy"]
    mag_c = ctrl[-1]["magnetic_energy"]
    metrics = [
        ["peak_current_reduction_pct", -pct(peak_c, peak_b), "max |native toroidal_current| scalar"],
        ["integrated_current_loading_change_pct", pct(int_c, int_b), "sum |native toroidal_current| over output times"],
        ["magnetic_energy_change_pct", pct(mag_c, mag_b), "final E_MP+E_MT+E_P from C1ke"],
        ["native_reconnected_flux_change_pct", pct(rf_c, rf_b), "final native /scalars/Reconnected_Flux"],
        ["topology_search_intermittency", "baseline and controlled have intermittent X-point/axis search misses", "diagnostic reliability warning"],
    ]
    with (OUT / "native_pair_metrics.csv").open("w", newline="") as f:
        w=csv.writer(f); w.writerow(["metric", "value", "definition"]); w.writerows(metrics)
    (OUT / "initialization_gate_baseline.json").write_text(json.dumps(gate(BASE, REPEAT), indent=2) + "\n")
    (OUT / "initialization_gate_controlled.json").write_text(json.dumps(gate(CTRL, None, BASE), indent=2) + "\n")
    (OUT / "baseline_topology_summary.json").write_text(json.dumps({
        "status": "PASS_WITH_INTERMITTENT_SEARCH_WARNING",
        "native_metric": "C1.h5:/scalars/Reconnected_Flux",
        "baseline_final_reconnected_flux": rf_b,
        "time_of_peak_current": max(base, key=lambda r: abs(r["toroidal_current"]))["time"],
        "xpoint_search": stdout_vals(BASE)["xpoint_found_count"],
        "xpoint_search_misses": stdout_vals(BASE)["xpoint_not_found_count"],
    }, indent=2) + "\n")
    rev_peak = max(abs(r["toroidal_current"]) for r in rev)
    with (OUT / "falsification_controls.csv").open("w", newline="") as f:
        w=csv.writer(f); w.writerow(["control", "status", "eps", "peak_current_proxy", "final_reconnected_flux", "interpretation"])
        w.writerow(["sign_reversed_eps", status(REV), read_eps(REV), rev_peak, rev[-1]["reconnected_flux"], "reconnected flux changes sign with eps; current proxy remains effectively unchanged"])
    (OUT / "resolution_check.csv").write_text("status,reason\nSKIPPED,no same-physical-state finer circle mesh was available; bundled 2K circle model changes the outer/resistive boundary geometry\n")
    classification = "NATIVE_TCT_NO_EFFECT"
    summary = {
        "classification": classification,
        "selected_case": "exploratory native GEM reconnection initializer on official RMP_nonlin single-part circle mesh carrier",
        "baseline_run": str(BASE), "controlled_run": str(CTRL), "falsification_run": str(REV),
        "actuator": "eps = 8.566360855e-4 versus baseline eps = 1e-3; native GEM magnetic-flux perturbation amplitude only",
        "baseline_peak_current_proxy": peak_b, "controlled_peak_current_proxy": peak_c,
        "peak_current_reduction_pct": -pct(peak_c, peak_b),
        "integrated_current_loading_change_pct": pct(int_c, int_b),
        "magnetic_energy_change_pct": pct(mag_c, mag_b),
        "native_reconnected_flux_change_pct": pct(rf_c, rf_b),
        "topology_result": "native Reconnected_Flux decreases in proportion to the deliberately reduced initial GEM perturbation amplitude; this is not accompanied by current-loading reduction and is reproduced as sign reversal under negative eps",
        "reliability_warning": "X-point/magnetic-axis search is intermittent on this coarse circular carrier mesh",
        "refinement": "Skipped: no same-physical-state finer mesh available in bundled artifacts",
    }
    (OUT / "native_pair_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "native_case_selection.md").write_text("""# Native GEM Case Selection\n\nSelected exploratory rung: native `itaylor = 3` GEM reconnection initializer on the official `RMP_nonlin` single-part circle mesh carrier, run with the real 2D executable.\n\nWhy: official `RMP_nonlin` 3D remains initialization-invalid on this host with the checked-in 16-part mesh, and the available splitter cannot regenerate the partition without an MPI launch. The GEM initializer is an upstream native reconnection path and emits the native `Reconnected_Flux` scalar.\n\nRejected alternatives:\n\n| candidate | result |\n|---|---|\n| `RMP_nonlin` checked-in 16-part 3D | invalid t=0 energy scale and rank killed by signal 9 |\n| regenerated `RMP_nonlin` 16-part mesh | local `split_smb` invocation aborted unless launched with enough MPI peers |\n| rectilinear GEM deck | failed because this build expects SCOREC model/mesh files |\n| bundled 2K circle mesh as refinement | rejected as same-physics refinement because its model changes wall/boundary geometry |\n\nThis is an exploratory native reconnection actuator-mapping rung, not an official regression result.\n""")
    (OUT / "actuator_definition.md").write_text("""# Actuator Definition\n\nChosen actuator: native GEM magnetic-flux perturbation amplitude `eps` in `C1input`.\n\nUpstream source path: `/home/ubuntu/M3DC1-official/unstructured/init_gem.f90`, `gem_reconnection_per`, where `eps*cos(akx*x)*cos(akz*z)` seeds the reconnecting flux perturbation.\n\nBaseline: `eps = 1e-3`.\n\nControlled: `eps = 8.566360855e-4 = 1e-3 * (1 - 0.14336391448782237)`, directly using the frozen BOUT peak-current reduction fraction.\n\nSign-reversed falsification: `eps = -8.566360855e-4`.\n\nNo amplitude sweep was run. Mesh, timestep, transport, executable, MPI layout, and output cadence were unchanged across baseline/control/falsification.\n""")
    (OUT / "topology_diagnostics.md").write_text("""# Topology Diagnostics\n\nPrimary native topology metric: `C1.h5:/scalars/Reconnected_Flux`, emitted by M3D-C1 diagnostics.\n\nSupporting native topology/search scalars: `psi0`, `psi_lcfs`, `psimin`, `xmag`, `zmag`, `xnull`, and `znull`.\n\nResult: reducing `eps` reduces the final native `Reconnected_Flux`, but this follows directly from reducing the initial GEM perturbation amplitude and does not reduce the current-loading proxy. The sign-reversed falsification flips the sign of `Reconnected_Flux` while leaving current nearly unchanged, supporting the interpretation that this rung measures seed-perturbation bookkeeping rather than a TCT current-loading effect.\n\nReliability warning: on this coarse circular mesh carrier, native magnetic-axis/X-point search is intermittent at some output times. The scalar trajectory is finite and repeatable, but this is not a strong topology-validation rung.\n""")
    (OUT / "M3DC1_TCT_NATIVE_GEM_REPORT.md").write_text(f"""# Native M3D-C1 GEM TCT Exploratory Rung\n\nPrimary classification: `{classification}`\n\nThis continuation tested a native GEM reconnection initializer after the official `RMP_nonlin` path remained invalid on this host. The controlled case changed only `eps`, the upstream GEM magnetic-flux perturbation amplitude.\n\n| metric | baseline | controlled | change |\n|---|---:|---:|---:|\n| peak current proxy | {peak_b:.8g} | {peak_c:.8g} | {-pct(peak_c, peak_b):.6g}% reduction |\n| integrated current proxy | {int_b:.8g} | {int_c:.8g} | {pct(int_c, int_b):.6g}% |\n| final magnetic energy | {mag_b:.8g} | {mag_c:.8g} | {pct(mag_c, mag_b):.6g}% |\n| final native Reconnected_Flux | {rf_b:.8g} | {rf_c:.8g} | {pct(rf_c, rf_b):.6g}% |\n\nInterpretation: the native topology scalar changes because the initial GEM perturbation amplitude was changed. It is not accompanied by a current-loading reduction, and the sign-reversed falsification confirms the response is dominated by perturbation-sign bookkeeping. This does not support the BOUT++ current-loading-reduction effect in this native GEM mapping.\n\nRefinement was skipped because no same-physical-state finer circle mesh was available in the bundled artifacts.\n""")
    for name, path in [("baseline", BASE), ("baseline_repeat", REPEAT), ("controlled", CTRL), ("falsification_reverse", REV), ("invalid_rmp_nonlin_checked_mesh", RMP_BAD_CHECKED), ("invalid_rmp_nonlin_regenerated_split", RMP_BAD_SPLIT)]:
        if path.exists(): compact(path, name)
    (OUT / "build_provenance.txt").write_text(run(["git", "rev-parse", "HEAD"], SRC) + run(["git", "status", "--short"], SRC) + "\n2D real build: /home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d\n")
    (OUT / "runtime_provenance.txt").write_text(json.dumps({"baseline": str(BASE), "baseline_repeat": str(REPEAT), "controlled": str(CTRL), "falsification_reverse": str(REV), "invalid_rmp_nonlin_checked_mesh": str(RMP_BAD_CHECKED), "invalid_rmp_nonlin_regenerated_split": str(RMP_BAD_SPLIT), "mpi_layout": "1 MPI rank for GEM 2D real single-part mesh carrier"}, indent=2) + "\n")
    (OUT / "launch_commands.sh").write_text("\n\n".join((p / "launch_command.sh").read_text() for p in [BASE, REPEAT, CTRL, REV] if (p / "launch_command.sh").exists()))
    shutil.copy2(Path(__file__), OUT / "extraction_scripts" / "extract_native_gem_pair.py")
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
