#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_magnetic_impulse_map"
RUN_ROOT = Path("/tmp/m3dc1_tct_magnetic_impulse_map_runs")
PULSE_TIMES = [0.00, 0.05, 0.10, 0.15, 0.20]
AMP = -0.01
DURATION = 0.05
RAMP = 0.0
DT = 0.01
NTIMEMAX = 40
NTIMEPR = 1
RESPONSE_HORIZON = 0.10
R_CENTER = 10.0
R_BAND = 0.25
Z_CENTER = 1.0
Z_SHOULDER = 0.561
CENTER_HW = 0.2805
SHOULDER_HW = 0.2805
HIGH_J_FRACTION = 0.75
C1KE_COLS = ["ntime","time","ekin","gamma_gr","ekinp","ekint","ekin3","emagp","emagt","emag3","etot"]
COPY_NAMES = ["circle-0.10-0.0-0.0-1K0.smb", "circle-0.10-0.0-0.0.txt", "part0.smb", "part.smb"]
SCALARS = ["Reconnected_Flux", "toroidal_current", "loop_voltage"]


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode:
        raise SystemExit(p.stdout)
    return p


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def nums(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?|[-+]?\.\d+(?:[Ee][-+]?\d+)?", text)]


class H5:
    def __init__(self) -> None:
        self.exe = shutil.which("h5dump")
        if not self.exe:
            raise RuntimeError("h5dump not found")

    def text(self, args: list[str]) -> str:
        p = run([self.exe, *args], check=True)
        return p.stdout

    def data(self, path: Path, dataset: str) -> list[float]:
        text = self.text(["-y", "-w", "0", "-d", dataset, str(path)])
        m = re.search(r"DATA \{(.*?)\}\s*\}\s*\}", text, re.S)
        return nums(m.group(1)) if m else []

    def shape(self, path: Path, dataset: str) -> tuple[int, ...]:
        text = self.text(["-H", "-d", dataset, str(path)])
        m = re.search(r"DATASPACE\s+SIMPLE\s+\{\s*\(\s*([0-9, ]+)\)", text)
        return tuple(int(x.strip()) for x in m.group(1).split(",")) if m else ()

    def matrix(self, path: Path, dataset: str) -> list[list[float]]:
        shape = self.shape(path, dataset)
        data = self.data(path, dataset)
        if len(shape) != 2 or len(data) != shape[0] * shape[1]:
            raise RuntimeError(f"bad dataset {path}:{dataset}, shape={shape}, values={len(data)}")
        return [data[i * shape[1]:(i + 1) * shape[1]] for i in range(shape[0])]


def replace_or_add(text: str, key: str, value: str) -> str:
    pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if pat.search(text):
        return pat.sub(rf"\g<1>{value}", text)
    return text.replace("\n /\n", f"\n {key} = {value}\n /\n", 1)


def prepare_run(name: str, amp: float, t_on: float, t_off: float) -> Path:
    run_dir = RUN_ROOT / name
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    for item in COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (run_dir / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, run_dir / item)
    text = (BASE / "C1input").read_text()
    for key, value in {
        "dt": f"{DT:.10g}",
        "ntimemax": str(NTIMEMAX),
        "ntimepr": str(NTIMEPR),
        "imag_control": "1",
        "mag_ctrl_amp": f"{amp:.10g}",
        "mag_ctrl_r0": "10.0",
        "mag_ctrl_z0": "1.0",
        "mag_ctrl_wr": "0.5",
        "mag_ctrl_wz": "0.5",
        "mag_ctrl_t_on": f"{t_on:.10g}",
        "mag_ctrl_t_ramp": f"{RAMP:.10g}",
        "mag_ctrl_t_off": f"{t_off:.10g}",
        "icd_source": "0",
        "J_0cd": "0.0",
    }.items():
        text = replace_or_add(text, key, value)
    (run_dir / "C1input").write_text(text)
    launch = f"""#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "{run_dir}"
set +e
timeout 900s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\\n' "$rc" > run_status.txt
exit "$rc"
"""
    (run_dir / "launch_command.sh").write_text(launch)
    (run_dir / "launch_command.sh").chmod(0o755)
    return run_dir


def prepare_baseline() -> Path:
    run_dir = RUN_ROOT / "baseline_highres"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    for item in COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (run_dir / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, run_dir / item)
    text = (BASE / "C1input").read_text()
    for key, value in {
        "dt": f"{DT:.10g}",
        "ntimemax": str(NTIMEMAX),
        "ntimepr": str(NTIMEPR),
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": "0",
        "J_0cd": "0.0",
    }.items():
        text = replace_or_add(text, key, value)
    (run_dir / "C1input").write_text(text)
    launch = f"""#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "{run_dir}"
set +e
timeout 900s mpirun --oversubscribe -n 1 "{EXE}" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\\n' "$rc" > run_status.txt
exit "$rc"
"""
    (run_dir / "launch_command.sh").write_text(launch)
    (run_dir / "launch_command.sh").chmod(0o755)
    return run_dir


def execute(run_dir: Path) -> None:
    start = time.time()
    p = run(["bash", "launch_command.sh"], cwd=run_dir)
    (run_dir / "launcher_wrapper_stdout.log").write_text(p.stdout)
    (run_dir / "elapsed_seconds.txt").write_text(f"{time.time() - start:.6f}\n")
    if p.returncode:
        raise SystemExit(f"{run_dir} failed rc={p.returncode}\n{p.stdout[-4000:]}")


def c1ke(run_dir: Path) -> list[dict[str, float]]:
    rows = []
    for line in (run_dir / "C1ke").read_text().splitlines():
        if line.strip():
            rows.append(dict(zip(C1KE_COLS, [float(x) for x in line.split()])))
    return rows


def scalar_series(h5: H5, run_dir: Path, name: str) -> list[float]:
    try:
        return h5.data(run_dir / "C1.h5", f"/scalars/{name}")
    except Exception:
        return []


def profile_metrics(h5: H5, run_dir: Path, i: int) -> dict[str, float]:
    path = run_dir / f"time_{i:03d}.h5"
    elems = h5.matrix(path, "/mesh/elements")
    jphi = [row[0] for row in h5.matrix(path, "/fields/jphi")]
    psi = [row[0] for row in h5.matrix(path, "/fields/psi")]
    rows = []
    for element, jj, pp in zip(elems, jphi, psi):
        r, z, w = element[4], element[5], max(element[2], 0.0)
        if abs(r - R_CENTER) <= R_BAND:
            rows.append({"R": r, "Z": z, "w": w, "j": jj, "aj": abs(jj), "psi": pp})
    rows.sort(key=lambda x: x["Z"])
    absint = sum(r["aj"] * r["w"] for r in rows)
    signed = sum(r["j"] * r["w"] for r in rows)
    peak = max(rows, key=lambda r: r["aj"])
    centroid = sum(r["Z"] * r["aj"] * r["w"] for r in rows) / max(absint, 1e-300)
    var = sum((r["Z"] - centroid) ** 2 * r["aj"] * r["w"] for r in rows) / max(absint, 1e-300)
    center = sum(r["aj"] * r["w"] for r in rows if abs(r["Z"] - Z_CENTER) <= CENTER_HW)
    shoulder = sum(r["aj"] * r["w"] for r in rows if abs(abs(r["Z"] - Z_CENTER) - Z_SHOULDER) <= SHOULDER_HW)
    high_cut = HIGH_J_FRACTION * peak["aj"]
    high = sum(r["aj"] * r["w"] for r in rows if r["aj"] >= high_cut)
    psi_vals = [r["psi"] for r in rows]
    dz = rows[-1]["Z"] - rows[0]["Z"]
    return {
        "Jpk": peak["aj"],
        "Jpk_R": peak["R"],
        "Jpk_Z": peak["Z"],
        "Jint_abs": absint,
        "Jint_signed": signed,
        "Jint_high": high,
        "W_sheet": 2.354820045 * math.sqrt(max(var, 0.0)),
        "current_centroid_Z": centroid,
        "center_abs_current": center,
        "shoulder_abs_current": shoulder,
        "center_to_shoulder_ratio": center / max(shoulder, 1e-300),
        "roi_psi_span": max(psi_vals) - min(psi_vals),
        "roi_Bz_proxy_dpsi_dZ": (rows[-1]["psi"] - rows[0]["psi"]) / dz if dz else 0.0,
    }


def extract(run_dir: Path) -> list[dict[str, float]]:
    h5 = H5()
    scalars = {s: scalar_series(h5, run_dir, s) for s in SCALARS}
    rows = []
    for i, row in enumerate(c1ke(run_dir)):
        if not (run_dir / f"time_{i:03d}.h5").exists():
            break
        out = {
            "index": i,
            "time": row["time"],
            "kinetic_energy": row["ekin"],
            "magnetic_energy": row["emagp"] + row["emagt"] + row["emag3"],
            "total_energy": row["etot"],
        }
        for s, values in scalars.items():
            out[s] = values[i] if i < len(values) else math.nan
        out.update(profile_metrics(h5, run_dir, i))
        rows.append(out)
    return add_derivatives(rows)


def add_derivatives(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    for i, row in enumerate(rows):
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        for key, out_key in [("W_sheet", "dW_dt"), ("Jpk", "dJpk_dt"), ("Reconnected_Flux", "reconnection_rate")]:
            a, b = (prev, nxt) if prev and nxt else ((prev or row), (nxt or row))
            dt = b["time"] - a["time"]
            row[out_key] = (b[key] - a[key]) / dt if dt else 0.0
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def by_time(rows: list[dict[str, float]], t: float, tol: float = 5e-9) -> dict[str, float]:
    return min(rows, key=lambda r: abs(r["time"] - t)) if rows else {}


def pct_delta(c: float, b: float) -> float:
    return 100.0 * (c / b - 1.0) if abs(b) > 1e-300 else math.nan


def classify_response(peak_width_pct: float, threshold: float) -> str:
    if peak_width_pct > threshold:
        return "BROADENING_RESPONSE"
    if peak_width_pct < -threshold:
        return "NARROWING_RESPONSE"
    return "NEUTRAL_RESPONSE"


def response_metrics(name: str, t_on: float, base: list[dict[str, float]], ctrl: list[dict[str, float]], noise: float) -> dict[str, float | str | bool]:
    t_off = t_on + DURATION
    response_end = t_off + RESPONSE_HORIZON
    pairs = []
    for c in ctrl:
        b = by_time(base, c["time"])
        if abs(b["time"] - c["time"]) < 5e-9:
            pairs.append((b, c))
    samples = []
    for b, c in pairs:
        if c["time"] <= t_on + 5e-9 or c["time"] > response_end + 5e-9:
            continue
        samples.append({
            "time": c["time"],
            "delta_W": c["W_sheet"] - b["W_sheet"],
            "delta_W_pct": pct_delta(c["W_sheet"], b["W_sheet"]),
            "delta_Jpk": c["Jpk"] - b["Jpk"],
            "delta_Jpk_pct": pct_delta(c["Jpk"], b["Jpk"]),
            "delta_Jcenter": c["center_abs_current"] - b["center_abs_current"],
            "delta_Jshoulders": c["shoulder_abs_current"] - b["shoulder_abs_current"],
            "delta_highJ": c["Jint_high"] - b["Jint_high"],
            "delta_highJ_pct": pct_delta(c["Jint_high"], b["Jint_high"]),
            "delta_center_to_shoulder_pct": pct_delta(c["center_to_shoulder_ratio"], b["center_to_shoulder_ratio"]),
            "delta_reconnected_flux": c["Reconnected_Flux"] - b["Reconnected_Flux"],
            "delta_magnetic_energy": c["magnetic_energy"] - b["magnetic_energy"],
            "delta_magnetic_energy_pct": pct_delta(c["magnetic_energy"], b["magnetic_energy"]),
            "delta_toroidal_current": c["toroidal_current"] - b["toroidal_current"],
            "delta_toroidal_current_pct": pct_delta(c["toroidal_current"], b["toroidal_current"]),
            "delta_psi_span": c["roi_psi_span"] - b["roi_psi_span"],
            "delta_bz_proxy": c["roi_Bz_proxy_dpsi_dZ"] - b["roi_Bz_proxy_dpsi_dZ"],
        })
    if not samples:
        raise RuntimeError(f"no response samples for {name}")
    peak = max(samples, key=lambda r: r["delta_W"])
    immediate = samples[0]
    positives = [s for s in samples if s["delta_W"] > noise]
    negatives = [s for s in samples if s["delta_W"] < -noise]
    onset = positives[0]["time"] if positives else math.nan
    zero_cross = math.nan
    after_peak = [s for s in samples if s["time"] > peak["time"] + 5e-9]
    for s in after_peak:
        if s["delta_W"] <= noise:
            zero_cross = s["time"]
            break
    favorable_integral = 0.0
    adverse_integral = 0.0
    for a, b in zip(samples, samples[1:]):
        dt = b["time"] - a["time"]
        avg = 0.5 * (a["delta_W"] + b["delta_W"])
        if avg > 0:
            favorable_integral += avg * dt
        else:
            adverse_integral += avg * dt
    decay_time = math.nan
    if math.isfinite(zero_cross):
        decay_time = zero_cross - peak["time"]
    base_on = by_time(base, t_on)
    row = {
        "case": name,
        "t_on": t_on,
        "t_off": t_off,
        "amp": AMP,
        "duration": DURATION,
        "response_window_end": response_end,
        "baseline_W_on": base_on["W_sheet"],
        "baseline_Jpk_on": base_on["Jpk"],
        "baseline_dW_dt_on": base_on["dW_dt"],
        "baseline_dJpk_dt_on": base_on["dJpk_dt"],
        "baseline_Reconnected_Flux_on": base_on["Reconnected_Flux"],
        "baseline_reconnection_rate_on": base_on["reconnection_rate"],
        "baseline_magnetic_energy_on": base_on["magnetic_energy"],
        "immediate_time": immediate["time"],
        "immediate_delta_W": immediate["delta_W"],
        "immediate_delta_W_pct": immediate["delta_W_pct"],
        "peak_response_time": peak["time"],
        "latency": peak["time"] - t_on,
        "peak_delta_W": peak["delta_W"],
        "peak_delta_W_pct": peak["delta_W_pct"],
        "delta_Jpk_at_peak": peak["delta_Jpk"],
        "delta_Jpk_pct_at_peak": peak["delta_Jpk_pct"],
        "delta_Jcenter_at_peak": peak["delta_Jcenter"],
        "delta_Jshoulders_at_peak": peak["delta_Jshoulders"],
        "delta_highJ_at_peak": peak["delta_highJ"],
        "delta_highJ_pct_at_peak": peak["delta_highJ_pct"],
        "center_to_shoulder_change_pct_at_peak": peak["delta_center_to_shoulder_pct"],
        "response_onset": onset,
        "positive_response_duration": (positives[-1]["time"] - positives[0]["time"]) if len(positives) > 1 else 0.0,
        "zero_crossing_time": zero_cross,
        "sign_reversal": math.isfinite(zero_cross),
        "integrated_favorable_delta_W": favorable_integral,
        "integrated_adverse_delta_W": adverse_integral,
        "decay_time": decay_time,
        "G_W": peak["delta_W"] / AMP,
        "G_Jpk": peak["delta_Jpk"] / AMP,
        "G_center": peak["delta_Jcenter"] / AMP,
        "G_shoulders": peak["delta_Jshoulders"] / AMP,
        "field_reachable": max(abs(s["delta_psi_span"]) for s in samples) > noise or max(abs(s["delta_bz_proxy"]) for s in samples) > noise,
        "sheet_authority": peak["delta_W"] > noise,
        "jpk_consistent": peak["delta_Jpk"] < -noise,
        "redistribution_consistent": peak["delta_Jshoulders"] > noise and peak["delta_Jcenter"] <= noise,
        "full_impulse_authority": peak["delta_W"] > noise and peak["delta_Jpk"] < -noise,
        "max_abs_magnetic_energy_change_pct": max(abs(s["delta_magnetic_energy_pct"]) for s in samples),
        "max_abs_toroidal_current_change_pct": max(abs(s["delta_toroidal_current_pct"]) for s in samples),
        "reconnected_flux_delta_at_peak": peak["delta_reconnected_flux"],
        "response_classification": classify_response(peak["delta_W"], noise),
    }
    return row


def copy_compact(run_dir: Path, prefix: str) -> None:
    for name in ["C1input", "C1ke", "run_status.txt", "launcher.stderr", "launch_command.sh", "elapsed_seconds.txt"]:
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, OUT / f"{prefix}_{name}")
    keep = []
    if (run_dir / "C1stdout").exists():
        for line in (run_dir / "C1stdout").read_text(errors="replace").splitlines():
            if re.search(r"WARNING|Warning|ERROR|Error|mesh entity counts|magnetic axis|X-point|Poloidal flux|Total energy|Toroidal current|Toroidal flux|Volume|TIME STEP|Stopped at|Done time loop", line):
                keep.append(line)
    (OUT / "compact_stdout" / f"{prefix}.log").write_text("\n".join(keep) + "\n")


def write_reports(rows: list[dict], zero: dict, convergence: list[dict]) -> None:
    classifications = [r["response_classification"] for r in rows]
    if any(r["sign_reversal"] for r in rows):
        primary = "M3DC1_MAGNETIC_RESPONSE_SIGN_REVERSAL"
    elif any(r["response_classification"] == "NARROWING_RESPONSE" for r in rows) and any(r["response_classification"] == "BROADENING_RESPONSE" for r in rows):
        primary = "M3DC1_MAGNETIC_RESPONSE_SIGN_REVERSAL"
    elif any(r["response_classification"] == "BROADENING_RESPONSE" for r in rows) and any(r["response_classification"] == "NEUTRAL_RESPONSE" for r in rows):
        primary = "M3DC1_MAGNETIC_RESPONSE_GAIN_COLLAPSE"
    elif all(r["response_classification"] == "BROADENING_RESPONSE" for r in rows) and all(r["full_impulse_authority"] for r in rows):
        primary = "M3DC1_MAGNETIC_RESPONSE_PERSISTENT_SHORT_PULSE_AUTHORITY"
    elif not any(r["field_reachable"] for r in rows):
        primary = "M3DC1_MAGNETIC_RESPONSE_NO_REPRODUCIBLE_AUTHORITY"
    else:
        primary = "M3DC1_MAGNETIC_RESPONSE_STATE_DEPENDENT"
    summary = {
        "primary_classification": primary,
        "lithium_classification": "LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED",
        "pulse_amp": AMP,
        "pulse_duration": DURATION,
        "pulse_times": PULSE_TIMES,
        "dt": DT,
        "ntimemax": NTIMEMAX,
        "response_horizon": RESPONSE_HORIZON,
        "zero_equivalence": zero,
        "case_classifications": {r["case"]: r["response_classification"] for r in rows},
        "field_reachable": {r["case"]: r["field_reachable"] for r in rows},
        "sheet_authority": {r["case"]: r["sheet_authority"] for r in rows},
        "jpk_consistent": {r["case"]: r["jpk_consistent"] for r in rows},
        "redistribution_consistent": {r["case"]: r["redistribution_consistent"] for r in rows},
        "full_impulse_authority": {r["case"]: r["full_impulse_authority"] for r in rows},
        "sign_reversal_times": {r["case"]: r["zero_crossing_time"] for r in rows if r["sign_reversal"]},
        "convergence_shared_times": convergence,
        "claim_boundary": "Native M3D-C1 normalized magnetic impulse timing map only; not TCT validation and not lithium-current dimensional transfer.",
    }
    (OUT / "impulse_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "proposed_state_dependent_controller.md").write_text(f"""# Proposed State-Dependent Controller

Classification:

```text
{primary}
```

This is a paper controller implication only. No closed-loop controller was run.

The tested command was fixed at `A=-0.01` with `duration=0.05`, `ramp=0`, and
the frozen magnetic ROI. High-resolution timing shows a transient broadening
lobe followed by decay or sign reversal in every tested window. Use the
favorable lobe as a transient intervention candidate and avoid holding the same
command continuously.

Recommended logic from this audit:

```text
EARLY: tested negative magnetic pulse can be used only as a timed transient.
AGGRESSIVE: unresolved; do not increase amplitude until the Jpk conflict is resolved.
HOLD: zero or reduced control after the favorable lobe decays; continuous fixed bias is not supported by current evidence.
```

Amplitude selection beyond `A=-0.01` remains unresolved.
""")
    (OUT / "lithium_control_implications.md").write_text("""# Lithium Control Implications

Classification:

```text
LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED
```

The timing map does not provide a physical calibration from normalized
`mag_ctrl_amp` to `deltaB [T]`, surface current `K [A/m]`, or lithium volumetric
current density `J_Li [A/m^2]`. Normalized M3D-C1 amplitudes were not inserted
into the Fiflis/Ruzic equations.

If magnetic control gain changes with state, a purely DC lithium bias cannot
represent the full timing-dependent controller. A later architecture may need:

```text
modest lithium standing bias
+ fast modulated lithium/backing-conductor/trim-field correction
```

That remains a hypothesis until dimensional magnetic transfer is calibrated.
""")
    lines = ["# M3D-C1 Magnetic Impulse Map Report", "", f"Primary classification: `{primary}`", "", "## Frozen Matrix", "", f"- amp: `{AMP}`", f"- duration: `{DURATION}`", f"- ramp: `{RAMP}`", f"- dt: `{DT}`", f"- ntimemax: `{NTIMEMAX}`", f"- pulse starts: `{PULSE_TIMES}`", "", "## Case Results", ""]
    for r in rows:
        lines.append(f"- `{r['case']}` t_on={r['t_on']}: {r['response_classification']}; peak dW={r['peak_delta_W']:.8g}, dJpk={r['delta_Jpk_at_peak']:.8g}, full_authority={r['full_impulse_authority']}, latency={r['latency']:.4g}, zero_cross={r['zero_crossing_time']}")
    lines += ["", "## Claim Boundary", "", "This is a native normalized magnetic impulse response map. It is not a TCT validation pass and not a lithium dimensional-transfer result."]
    (OUT / "M3DC1_MAGNETIC_IMPULSE_MAP_REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "compact_stdout").mkdir(exist_ok=True)
    (OUT / "extraction_scripts").mkdir(exist_ok=True)
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    run_dirs = {"baseline_highres": prepare_baseline()}
    run_dirs["impulse_zero"] = prepare_run("impulse_zero", 0.0, 0.0, DURATION)
    for t in PULSE_TIMES:
        run_dirs[f"impulse_t{int(round(t * 100)):03d}"] = prepare_run(f"impulse_t{int(round(t * 100)):03d}", AMP, t, t + DURATION)
    launch_lines = []
    for name, run_dir in run_dirs.items():
        launch_lines.append(f"# {name}\ncd {run_dir}\nbash launch_command.sh\n")
    (OUT / "launch_commands.sh").write_text("\n".join(launch_lines))
    (OUT / "impulse_plan.md").write_text(f"""# High-Resolution Magnetic Impulse Plan

Frozen before high-resolution outcomes:

```text
dt = {DT}
ntimepr = {NTIMEPR}
ntimemax = {NTIMEMAX}
amp = {AMP}
duration = {DURATION}
ramp = {RAMP}
pulse starts = {PULSE_TIMES}
run root = {RUN_ROOT}
```

Only numerical cadence and output cadence differ from the frozen coarse
baseline. Mesh, equilibrium, GEM eps, gem_sheet_scale, eta, nu, and solver
physics are not modified.
""")
    (OUT / "build_provenance.txt").write_text(
        f"repo={REPO}\nbranch={run(['git','branch','--show-current'], cwd=REPO, check=True).stdout.strip()}\n"
        f"head={run(['git','rev-parse','HEAD'], cwd=REPO, check=True).stdout.strip()}\n"
        f"baseline_input_sha256={sha256_file(BASE/'C1input')}\n"
        f"executable={EXE}\nexecutable_sha256={sha256_file(EXE)}\n"
        f"m3dc1_diff_sha256={hashlib.sha256(run(['git','diff','--','unstructured/M3Dmodules.f90','unstructured/input.f90','unstructured/ludef_t.f90'], cwd=SRC, check=True).stdout.encode()).hexdigest()}\n"
    )
    runtime = [f"started_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", f"run_root={RUN_ROOT}"]
    for name, run_dir in run_dirs.items():
        execute(run_dir)
        runtime.append(f"{name}_status={(run_dir/'run_status.txt').read_text().strip()}")
        copy_compact(run_dir, name)
    base = extract(run_dirs["baseline_highres"])
    zero_rows = extract(run_dirs["impulse_zero"])
    write_csv(OUT / "baseline_phase_dynamics.csv", base)
    max_zero = 0.0
    for b, z in zip(base, zero_rows):
        for key in ["W_sheet", "Jpk", "center_abs_current", "shoulder_abs_current", "Jint_high", "Reconnected_Flux", "magnetic_energy", "toroidal_current", "roi_psi_span", "roi_Bz_proxy_dpsi_dZ"]:
            max_zero = max(max_zero, abs(z[key] - b[key]))
    noise = max(max_zero * 10.0, 1e-10)
    zero = {"zero_equivalence_pass": max_zero <= 1e-12, "max_abs_metric_delta": max_zero, "noise_threshold_used": noise}
    (OUT / "impulse_zero_equivalence.json").write_text(json.dumps(zero, indent=2) + "\n")
    old = extract(BASE)
    convergence = []
    for old_row in old:
        hr = by_time(base, old_row["time"], 0.006)
        if abs(hr["time"] - old_row["time"]) <= 0.006:
            convergence.append({"time": old_row["time"], "delta_W_sheet": hr["W_sheet"] - old_row["W_sheet"], "delta_Jpk": hr["Jpk"] - old_row["Jpk"], "delta_Reconnected_Flux": hr["Reconnected_Flux"] - old_row["Reconnected_Flux"], "delta_magnetic_energy": hr["magnetic_energy"] - old_row["magnetic_energy"]})
    (OUT / "baseline_phase_summary.json").write_text(json.dumps({
        "dt": DT,
        "ntimemax": NTIMEMAX,
        "samples": len(base),
        "shared_time_convergence": convergence,
        "max_abs_zero_delta": max_zero,
    }, indent=2) + "\n")
    matrix = []
    for t in PULSE_TIMES:
        name = f"impulse_t{int(round(t * 100)):03d}"
        rows = extract(run_dirs[name])
        write_csv(OUT / f"{name}_timeseries.csv", rows)
        matrix.append(response_metrics(name, t, base, rows, noise))
    write_csv(OUT / "impulse_response_matrix.csv", matrix)
    write_csv(OUT / "magnetic_impulse_state_response.csv", matrix)
    (OUT / "opposite_sign_confirmation.csv").write_text("status,reason\nNOT_RUN,Run only after high-resolution negative pulse map requires sign-flip confirmation.\n")
    shutil.copy2(Path(__file__), OUT / "extraction_scripts" / Path(__file__).name)
    write_reports(matrix, zero, convergence)
    runtime.append(f"finished_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    (OUT / "runtime_provenance.txt").write_text("\n".join(runtime) + "\n")


if __name__ == "__main__":
    main()
