#!/usr/bin/env python3
"""Source=0 M3D-C1 restart transport equivalence audit.

No TCT actuator is enabled. One uninterrupted trajectory is compared with a
source=0 chain restarted at t=0.10, 0.15, 0.20, and 0.30. The chain must
advance state, reach each stop time, and reproduce equal-time observables.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_restart_transport_audit"
RUN_ROOT = Path("/tmp/m3dc1_restart_transport_audit_runs")

DT = 0.01
HORIZON = 0.30
BOUNDARIES = (0.10, 0.15, 0.20, 0.30)
ABS_TOL = 1e-12
REL_TOL = 1e-10
TIME_TOL = 1e-8
METRICS = (
    "W_sheet", "Jpk", "Jint_high", "center_abs_current",
    "shoulder_abs_current", "Reconnected_Flux", "magnetic_energy",
)
EXECUTION_FILES = {
    "C1input", "launch_command.sh", "C1stdout", "launcher.stderr",
    "run_status.txt", "wrapper_stdout.log", "elapsed_seconds.txt",
    "restart_seed_manifest.json", "segment_result.json",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def diagnostic(name: str) -> bool:
    return name == "C1ke" or name.startswith("time_")


def prepare(name: str, restart: int, stop: float) -> Path:
    d = RUN_ROOT / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for item in pta.COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)

    text = (BASE / "C1input").read_text()
    values = {
        "dt": f"{DT:.10g}",
        "ntimemax": str(int(round(stop / DT))),
        "ntimepr": "1",
        "irestart": str(restart),
        "irestart_slice": "-1",
        "iwrite_restart": "1",
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": "0",
        "J_0cd": "0.0",
    }
    for key, value in values.items():
        text = pta.replace_or_add(text, key, value)
    (d / "C1input").write_text(text)

    launch = f'''#!/usr/bin/env bash
set -euo pipefail
export TMPDIR="${{TMPDIR:-/tmp/tct-$USER}}"
export OMPI_MCA_orte_tmpdir_base="${{OMPI_MCA_orte_tmpdir_base:-$TMPDIR}}"
mkdir -p "$TMPDIR" "$OMPI_MCA_orte_tmpdir_base"
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
    (d / "launch_command.sh").write_text(launch)
    (d / "launch_command.sh").chmod(0o755)
    return d


def copy_restart(previous: Path, current: Path) -> dict:
    """Copy full non-diagnostic state, excluding stale C1ke/time_*.h5."""
    source = previous / "C1.h5"
    if not source.exists():
        raise RuntimeError(f"missing restart source {source}")
    copied, skipped = [], []
    for item in sorted(previous.iterdir(), key=lambda p: p.name):
        if item.name in EXECUTION_FILES or diagnostic(item.name):
            skipped.append(item.name)
            continue
        target = current / item.name
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        if item.is_symlink():
            target.symlink_to(item.readlink())
        elif item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        copied.append(item.name)

    target = current / "C1.h5"
    if not target.exists():
        raise RuntimeError("restart payload did not include C1.h5")
    stale = [p.name for p in current.iterdir() if diagnostic(p.name)]
    if stale:
        raise RuntimeError("stale diagnostics before restart: " + ", ".join(stale))
    manifest = {
        "source_directory": str(previous),
        "source_C1_sha256": sha256(source),
        "seed_C1_sha256": sha256(target),
        "copied": copied,
        "skipped": skipped,
        "policy": "all non-diagnostic prior state; no C1ke/time_*.h5",
    }
    dump(current / "restart_seed_manifest.json", manifest)
    return manifest


def execute(d: Path) -> dict:
    t0 = time.time()
    p = pta.sh(["bash", "launch_command.sh"], cwd=d)
    status = {
        "return_code": p.returncode,
        "elapsed_seconds": time.time() - t0,
        "wrapper_tail": p.stdout[-5000:],
        "C1stdout_tail": (d / "C1stdout").read_text(errors="replace")[-5000:]
        if (d / "C1stdout").exists() else "",
        "launcher_stderr_tail": (d / "launcher.stderr").read_text(errors="replace")[-5000:]
        if (d / "launcher.stderr").exists() else "",
    }
    dump(d / "segment_result.json", status)
    return status


def profile(h5: pta.H5, path: Path) -> dict[str, float]:
    elems = h5.matrix(path, "/mesh/elements")
    jphi = [r[0] for r in h5.matrix(path, "/fields/jphi")]
    rows = []
    for e, j in zip(elems, jphi):
        r, z, w = e[4], e[5], max(e[2], 0.0)
        if abs(r - pta.R_CENTER) <= pta.R_BAND:
            rows.append((z, w, abs(j)))
    if not rows:
        raise RuntimeError(f"empty sheet ROI in {path}")
    absint = sum(a * w for _, w, a in rows)
    jpk = max(a for _, _, a in rows)
    centroid = sum(z * a * w for z, w, a in rows) / max(absint, 1e-300)
    var = sum((z - centroid) ** 2 * a * w for z, w, a in rows) / max(absint, 1e-300)
    center = sum(a*w for z, w, a in rows if abs(z-pta.Z_CENTER) <= pta.CENTER_HW)
    shoulder = sum(a*w for z, w, a in rows if abs(abs(z-pta.Z_CENTER)-pta.Z_SHOULDER) <= pta.SHOULDER_HW)
    high = sum(a*w for _, w, a in rows if a >= pta.HIGH_J_FRACTION * jpk)
    return {
        "Jpk": jpk,
        "W_sheet": 2.354820045 * math.sqrt(max(var, 0.0)),
        "Jint_high": high,
        "center_abs_current": center,
        "shoulder_abs_current": shoulder,
    }


def extract(d: Path) -> list[dict[str, float]]:
    """Use only fresh diagnostics; tolerate global restart file numbering."""
    h5 = pta.H5()
    krows = pta.c1ke(d)
    files = sorted(d.glob("time_*.h5"))
    if len(files) < len(krows):
        raise RuntimeError(f"C1ke/time file mismatch: {len(krows)} rows, {len(files)} files")
    flux = h5.data(d / "C1.h5", "/scalars/Reconnected_Flux")
    out = []
    for i, (k, time_file) in enumerate(zip(krows, files)):
        ntime = int(round(float(k.get("ntime", i))))
        fi = ntime if 0 <= ntime < len(flux) else i
        row = {
            "time": float(k["time"]),
            "magnetic_energy": float(k["emagp"] + k["emagt"] + k["emag3"]),
            "Reconnected_Flux": float(flux[fi]) if fi < len(flux) else math.nan,
        }
        row.update(profile(h5, time_file))
        out.append(row)
    return out


def nearest(rows: list[dict[str, float]], t: float) -> dict[str, float]:
    return min(rows, key=lambda r: abs(r["time"] - t))


def compare(seg: dict[str, float], base: dict[str, float], t: float) -> dict:
    result = {"time": t, "pass": True, "by_metric": {}}
    max_abs, max_scaled = 0.0, 0.0
    for key in METRICS:
        a, b = float(seg[key]), float(base[key])
        delta = a - b
        tol = ABS_TOL + REL_TOL * max(abs(a), abs(b), 1.0)
        ok = math.isfinite(delta) and abs(delta) <= tol
        scaled = abs(delta) / tol if tol else math.inf
        result["by_metric"][key] = {
            "baseline": b, "segmented": a, "delta": delta,
            "tolerance": tol, "scaled_error": scaled, "pass": ok,
        }
        result["pass"] = result["pass"] and ok
        max_abs, max_scaled = max(max_abs, abs(delta)), max(max_scaled, scaled)
    result["max_abs_metric_delta"] = max_abs
    result["max_scaled_error"] = max_scaled
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    report = {
        "audit": {
            "type": "native_source0_restart_transport_equivalence",
            "dt": DT, "horizon": HORIZON, "boundaries": list(BOUNDARIES),
            "source": 0, "actuation": "none",
            "abs_tol": ABS_TOL, "rel_tol": REL_TOL, "metrics": list(METRICS),
            "restart_policy": "all non-diagnostic prior state; no C1ke/time_*.h5",
        },
        "segments": [], "equivalence_checks": [],
        "claim_boundary": "Restart mechanics only; no TCT control claim is tested.",
    }

    baseline = prepare("baseline_continuous", 0, HORIZON)
    print("[restart-audit] uninterrupted source=0 baseline", flush=True)
    bstatus = execute(baseline)
    report["baseline"] = {"directory": str(baseline), "execution": bstatus}
    if bstatus["return_code"]:
        report["classification"] = "M3DC1_RESTART_AUDIT_BASELINE_FAILED"
        dump(OUT / "restart_transport_summary.json", report)
        return 2
    brows = extract(baseline)

    previous = None
    previous_stop = 0.0
    combined = []
    chain_ok = True
    for i, stop in enumerate(BOUNDARIES):
        restart = int(i > 0)
        d = prepare(f"segment_{i:02d}_{previous_stop:.2f}_{stop:.2f}", restart, stop)
        manifest = None
        previous_hash = None
        if previous is not None:
            previous_hash = sha256(previous / "C1.h5")
            manifest = copy_restart(previous, d)
        print(f"[restart-audit] segment {i} {previous_stop:.2f}->{stop:.2f} restart={restart}", flush=True)
        status = execute(d)
        item = {
            "index": i, "start": previous_stop, "stop": stop,
            "restart": bool(restart), "directory": str(d),
            "execution": status, "seed_manifest": manifest,
        }
        if status["return_code"]:
            item.update(pass_=False, error=f"native rc={status['return_code']}")
            item["pass"] = False
            report["segments"].append(item)
            chain_ok = False
            break
        if not (d / "C1.h5").exists():
            item.update({"pass": False, "error": "missing final C1.h5"})
            report["segments"].append(item)
            chain_ok = False
            break

        final_hash = sha256(d / "C1.h5")
        if restart:
            seed_hash = manifest["seed_C1_sha256"]
            item["seed_matches_previous_final"] = (
                seed_hash == previous_hash == manifest["source_C1_sha256"]
            )
            item["state_hash_advanced"] = final_hash != seed_hash
        else:
            item["seed_matches_previous_final"] = True
            item["state_hash_advanced"] = True
        item["final_C1_sha256"] = final_hash

        try:
            rows = extract(d)
        except Exception as exc:
            item.update({"pass": False, "error": f"extract failed: {exc}"})
            report["segments"].append(item)
            chain_ok = False
            break
        if restart:
            rows = [r for r in rows if r["time"] > previous_stop + TIME_TOL]
        if not rows:
            item.update({"pass": False, "error": "no advanced fresh diagnostics"})
            report["segments"].append(item)
            chain_ok = False
            break
        last = max(r["time"] for r in rows)
        item["last_extracted_time"] = last
        item["time_advanced_to_stop"] = abs(last - stop) <= TIME_TOL
        item["pass"] = all((item["seed_matches_previous_final"], item["state_hash_advanced"], item["time_advanced_to_stop"]))
        report["segments"].append(item)
        chain_ok = chain_ok and item["pass"]
        combined.extend(rows)
        previous, previous_stop = d, stop

    report["restart_chain_execution_pass"] = chain_ok and len(report["segments"]) == len(BOUNDARIES)
    if report["restart_chain_execution_pass"]:
        for t in BOUNDARIES:
            s, b = nearest(combined, t), nearest(brows, t)
            if abs(s["time"] - t) > TIME_TOL or abs(b["time"] - t) > TIME_TOL:
                report["equivalence_checks"].append({"time": t, "pass": False, "error": "missing equal-time sample"})
            else:
                report["equivalence_checks"].append(compare(s, b, t))

    eq = len(report["equivalence_checks"]) == len(BOUNDARIES) and all(c.get("pass") for c in report["equivalence_checks"])
    report["equal_time_metric_equivalence_pass"] = eq
    if report["restart_chain_execution_pass"] and previous is not None:
        report["final_state_hash_comparison"] = {
            "baseline_C1_sha256": sha256(baseline / "C1.h5"),
            "segmented_C1_sha256": sha256(previous / "C1.h5"),
        }
        report["final_state_hash_comparison"]["exact_match"] = (
            report["final_state_hash_comparison"]["baseline_C1_sha256"]
            == report["final_state_hash_comparison"]["segmented_C1_sha256"]
        )

    if report["restart_chain_execution_pass"] and eq:
        report["classification"], rc = "M3DC1_SOURCE0_RESTART_TRANSPORT_EQUIVALENCE_PASS", 0
    elif report["restart_chain_execution_pass"]:
        report["classification"], rc = "M3DC1_SOURCE0_RESTART_TRANSPORT_METRIC_MISMATCH", 4
    else:
        report["classification"], rc = "M3DC1_SOURCE0_RESTART_TRANSPORT_EXECUTION_FAILED", 3

    dump(OUT / "restart_transport_summary.json", report)
    (OUT / "runtime_provenance.txt").write_text(
        f"repo={REPO}\nbaseline={BASE}\nsource={SRC}\nexecutable={EXE}\n"
        f"executable_sha256={pta.sha256_file(EXE)}\nrun_root={RUN_ROOT}\n"
        f"dt={DT}\nhorizon={HORIZON}\nboundaries={list(BOUNDARIES)}\n"
        f"source_mode=0\nactuation=none\nabs_tol={ABS_TOL}\nrel_tol={REL_TOL}\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
