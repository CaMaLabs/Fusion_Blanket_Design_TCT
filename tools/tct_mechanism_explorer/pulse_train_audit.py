#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path("/home/ubuntu/work/openmc/sweep")
SRC = Path("/home/ubuntu/M3DC1-official")
BUILD = SRC / "build-ubuntu-2d"
EXE = BUILD / "unstructured/m3dc1_2d"
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
OUT = REPO / "validation_runs/m3dc1_tct_magnetic_pulse_train"
RUN_ROOT = Path("/tmp/m3dc1_tct_magnetic_pulse_train_runs")

AMP = -0.01
DT = 0.01
NTIMEMAX = 40
NTIMEPR = 1
TRAIN_START = 0.0
TRAIN_END = 0.35
RAMP = 0.0
R_CENTER = 10.0
R_BAND = 0.25
Z_CENTER = 1.0
Z_SHOULDER = 0.561
CENTER_HW = 0.2805
SHOULDER_HW = 0.2805
HIGH_J_FRACTION = 0.75

# Frozen before any pulse-train outcomes are observed.
CASES = [
    {"name": "single_reference", "period": 0.0, "pulse_width": 0.0, "t_off": 0.05},
    {"name": "train_p040_w020", "period": 0.04, "pulse_width": 0.02, "t_off": TRAIN_END},
    {"name": "train_p050_w020", "period": 0.05, "pulse_width": 0.02, "t_off": TRAIN_END},
    {"name": "train_p060_w020", "period": 0.06, "pulse_width": 0.02, "t_off": TRAIN_END},
    {"name": "train_p050_w030", "period": 0.05, "pulse_width": 0.03, "t_off": TRAIN_END},
]

WIDTH_GAIN_THRESHOLD_PCT = 0.02
POSITIVE_WIDTH_FRACTION_THRESHOLD = 0.60
HIGH_J_IMPROVEMENT_THRESHOLD_PCT = -0.01
JPK_WORSENING_TOLERANCE_PCT = 0.10
ZERO_ABS_TOL = 1e-12

C1KE_COLS = [
    "ntime", "time", "ekin", "gamma_gr", "ekinp", "ekint", "ekin3",
    "emagp", "emagt", "emag3", "etot",
]
COPY_NAMES = [
    "circle-0.10-0.0-0.0-1K0.smb",
    "circle-0.10-0.0-0.0.txt",
    "part0.smb",
    "part.smb",
]


def sh(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n{p.stdout}")
    return p


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_or_add(text: str, key: str, value: str) -> str:
    pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if pat.search(text):
        return pat.sub(rf"\g<1>{value}", text)
    return text.replace("\n /\n", f"\n {key} = {value}\n /\n", 1)


def install_operator() -> bool:
    """Idempotently extend the existing imag_control source with periodic pulse timing."""
    modules = SRC / "unstructured/M3Dmodules.f90"
    inputf = SRC / "unstructured/input.f90"
    ludef = SRC / "unstructured/ludef_t.f90"
    for p in (modules, inputf, ludef):
        if not p.exists():
            raise FileNotFoundError(p)

    changed = False

    text = modules.read_text()
    if "mag_ctrl_amp" not in text:
        anchor = re.search(r"^\s*real\s*::\s*delta_cd\b[^\n]*$", text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cannot locate module declaration anchor delta_cd")
        decl = (
            anchor.group(0)
            + "\n  integer :: imag_control ! 1 = localized magnetic flux/vector-potential source"
            + "\n  real :: mag_ctrl_amp, mag_ctrl_r0, mag_ctrl_z0"
            + "\n  real :: mag_ctrl_wr, mag_ctrl_wz"
            + "\n  real :: mag_ctrl_t_on, mag_ctrl_t_ramp, mag_ctrl_t_off"
        )
        text = text[:anchor.start()] + decl + text[anchor.end():]
        modules.write_text(text)
        changed = True
    if "mag_ctrl_period" not in text:
        anchor = re.search(r"^\s*real\s*::\s*mag_ctrl_t_off\b[^\n]*$", text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cannot locate magnetic module declarations")
        decl = (
            anchor.group(0)
            + "\n  real :: mag_ctrl_period"
            + "\n  real :: mag_ctrl_pulse_width"
        )
        text = text[:anchor.start()] + decl + text[anchor.end():]
        modules.write_text(text)
        changed = True

    text = inputf.read_text()
    if '"mag_ctrl_amp"' not in text:
        anchor = re.search(r'^\s*call add_var_double\("delta_cd"[^\n]*\n(?:[^\n]*\n){0,2}', text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cannot locate delta_cd registration anchor")
        regs = (
            anchor.group(0)
            + '  call add_var_int("imag_control", imag_control, 0, &\n'
            + '       "1: localized magnetic flux/vector-potential control source", source_grp)\n'
            + '  call add_var_double("mag_ctrl_amp", mag_ctrl_amp, 0., &\n'
            + '       "localized magnetic control amplitude", source_grp)\n'
            + '  call add_var_double("mag_ctrl_r0", mag_ctrl_r0, 10., &\n'
            + '       "R-coordinate of magnetic control center", source_grp)\n'
            + '  call add_var_double("mag_ctrl_z0", mag_ctrl_z0, 1., &\n'
            + '       "Z-coordinate of magnetic control center", source_grp)\n'
            + '  call add_var_double("mag_ctrl_wr", mag_ctrl_wr, 0.5, &\n'
            + '       "R-width of magnetic control source", source_grp)\n'
            + '  call add_var_double("mag_ctrl_wz", mag_ctrl_wz, 0.5, &\n'
            + '       "Z-width of magnetic control source", source_grp)\n'
            + '  call add_var_double("mag_ctrl_t_on", mag_ctrl_t_on, 0., &\n'
            + '       "time when magnetic control turns on", source_grp)\n'
            + '  call add_var_double("mag_ctrl_t_ramp", mag_ctrl_t_ramp, 0., &\n'
            + '       "smooth magnetic-control ramp duration", source_grp)\n'
            + '  call add_var_double("mag_ctrl_t_off", mag_ctrl_t_off, 1.e30, &\n'
            + '       "time when magnetic control turns off", source_grp)\n'
        )
        text = text[:anchor.start()] + regs + text[anchor.end():]
        inputf.write_text(text)
        changed = True
    if '"mag_ctrl_period"' not in text:
        anchor = re.search(r'^\s*call add_var_double\("mag_ctrl_t_off"[^\n]*\n(?:[^\n]*\n){0,1}', text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cannot locate magnetic input registrations")
        regs = (
            anchor.group(0)
            + '  call add_var_double("mag_ctrl_period", mag_ctrl_period, 0., &\n'
            + '       "period of repeated magnetic-control pulses; <=0 selects single gate", source_grp)\n'
            + '  call add_var_double("mag_ctrl_pulse_width", mag_ctrl_pulse_width, 0., &\n'
            + '       "on-time within each repeated magnetic-control period", source_grp)\n'
        )
        text = text[:anchor.start()] + regs + text[anchor.end():]
        inputf.write_text(text)
        changed = True

    text = ludef.read_text()
    # Match the native magnetic-control block independent of indentation or
    # spacing style used by the particular official checkout.
    start_match = re.search(
        # Official source revisions differ in spacing, decimal spelling, and
        # whether the condition is split across continuation lines.  Anchor
        # on the two semantic control symbols and the executable IF/THEN.
        r"^\s*if\b(?=[^\n]*\bimag_control\b)"
        r"(?=[^\n]*\bmag_ctrl_amp\b)[^\n]*\bthen\b",
        text, re.I | re.M,
    )
    if not start_match:
        # Some official trees keep this included fragment under a different
        # filename. Search the actual unstructured source set before failing.
        root = SRC / "unstructured"
        for candidate in sorted(root.rglob("*")):
            if (candidate == ludef or not candidate.is_file()
                    or candidate.suffix.lower() not in {".f90", ".f", ".inc"}):
                continue
            try:
                candidate_text = candidate.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            candidate_match = re.search(
                r"^\s*if\b(?=[^\n]*\bimag_control\b)"
                r"(?=[^\n]*\bmag_ctrl_amp\b)[^\n]*\bthen\b",
                candidate_text, re.I | re.M,
            )
            if candidate_match:
                ludef, text, start_match = candidate, candidate_text, candidate_match
                break
    if not start_match:
        raise RuntimeError("native imag_control/mag_ctrl_amp source block not found under unstructured/")
    start = start_match.start()
    end_match = re.search(
        r"^\s*if\b(?=[^\n]*\bicd_source\b)[^\n]*\bthen\b",
        text[start_match.end():], re.I | re.M,
    )
    if not end_match:
        raise RuntimeError("icd_source boundary not found after magnetic block in ludef_t.f90")
    end = start_match.end() + end_match.start()
    block = text[start:end]
    if "mag_ctrl_period.gt.0." not in block:
        new_block = """  if(imag_control.eq.1 .and. mag_ctrl_amp.ne.0.) then
     if(time.lt.mag_ctrl_t_on .or. time.ge.mag_ctrl_t_off) then
        mag_gate = 0.
     else if(mag_ctrl_period.gt.0. .and. mag_ctrl_pulse_width.gt.0.) then
        mag_tau = modulo(time-mag_ctrl_t_on, mag_ctrl_period)
        if(mag_tau.ge.mag_ctrl_pulse_width) then
           mag_gate = 0.
        else if(mag_ctrl_t_ramp.gt.0. .and. mag_tau.lt.mag_ctrl_t_ramp) then
           mag_tau = mag_tau/mag_ctrl_t_ramp
           mag_gate = mag_tau*mag_tau*(3. - 2.*mag_tau)
        else
           mag_gate = 1.
        end if
     else if(mag_ctrl_t_ramp.gt.0. .and. time.lt.mag_ctrl_t_on+mag_ctrl_t_ramp) then
        mag_tau = (time-mag_ctrl_t_on)/mag_ctrl_t_ramp
        mag_gate = mag_tau*mag_tau*(3. - 2.*mag_tau)
     else
        mag_gate = 1.
     end if
     if(mag_gate.ne.0.) then
        mag_wr = max(mag_ctrl_wr, 1.e-30)
        mag_wz = max(mag_ctrl_wz, 1.e-30)
        do j=1,npoints
           temp79a(j) = mag_gate * mag_ctrl_amp * &
                exp( -(x_79(j)-mag_ctrl_r0)**2/mag_wr**2 &
                - (z_79(j)-mag_ctrl_z0)**2/mag_wz**2 )
        enddo
        r4term = r4term + dt*intx2(trialx(:,:,OP_1),temp79a)
     end if
  endif"""
        text = text[:start] + new_block + text[end:]
        changed = True

    ludef.write_text(text)
    return changed


def build() -> None:
    if not BUILD.exists():
        raise FileNotFoundError(BUILD)
    p = sh(["cmake", "--build", str(BUILD), "--target", "m3dc1_2d", "-j2"])
    if p.returncode:
        raise RuntimeError(p.stdout[-12000:])
    if not EXE.exists():
        raise RuntimeError(f"build completed but executable missing: {EXE}")


def copy_mesh_assets(d: Path) -> None:
    for item in COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)


def launch_script(d: Path) -> None:
    launch = f'''#!/usr/bin/env bash
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
    (d / "launch_command.sh").write_text(launch)
    (d / "launch_command.sh").chmod(0o755)


def prepare_dir(name: str, amp: float, period: float, pulse_width: float, t_off: float) -> Path:
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
        "imag_control": "1",
        "mag_ctrl_amp": f"{amp:.10g}",
        "mag_ctrl_r0": "10.0",
        "mag_ctrl_z0": "1.0",
        "mag_ctrl_wr": "0.5",
        "mag_ctrl_wz": "0.5",
        "mag_ctrl_t_on": f"{TRAIN_START:.10g}",
        "mag_ctrl_t_ramp": f"{RAMP:.10g}",
        "mag_ctrl_t_off": f"{t_off:.10g}",
        "mag_ctrl_period": f"{period:.10g}",
        "mag_ctrl_pulse_width": f"{pulse_width:.10g}",
        "icd_source": "0",
        "J_0cd": "0.0",
    }
    for k, v in updates.items():
        text = replace_or_add(text, k, v)
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
    for k, v in {
        "dt": f"{DT:.10g}",
        "ntimemax": str(NTIMEMAX),
        "ntimepr": str(NTIMEPR),
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": "0",
        "J_0cd": "0.0",
    }.items():
        text = replace_or_add(text, k, v)
    (d / "C1input").write_text(text)
    launch_script(d)
    return d


def execute(d: Path) -> None:
    t0 = time.time()
    p = sh(["bash", "launch_command.sh"], cwd=d)
    (d / "wrapper_stdout.log").write_text(p.stdout)
    (d / "elapsed_seconds.txt").write_text(f"{time.time()-t0:.6f}\n")
    if p.returncode:
        raise RuntimeError(f"{d.name} failed rc={p.returncode}\n{p.stdout[-4000:]}")


def nums(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?|[-+]?\.\d+(?:[Ee][-+]?\d+)?", text)]


class H5:
    def __init__(self) -> None:
        self.exe = shutil.which("h5dump")
        if not self.exe:
            raise RuntimeError("h5dump not found; activate m3dc1-deps")

    def text(self, args: list[str]) -> str:
        return sh([self.exe, *args], check=True).stdout

    def data(self, path: Path, dataset: str) -> list[float]:
        txt = self.text(["-y", "-w", "0", "-d", dataset, str(path)])
        m = re.search(r"DATA \{(.*?)\}\s*\}\s*\}", txt, re.S)
        return nums(m.group(1)) if m else []

    def matrix(self, path: Path, dataset: str) -> list[list[float]]:
        hdr = self.text(["-H", "-d", dataset, str(path)])
        m = re.search(r"DATASPACE\s+SIMPLE\s+\{\s*\(\s*([0-9, ]+)\)", hdr)
        shape = tuple(int(x.strip()) for x in m.group(1).split(",")) if m else ()
        data = self.data(path, dataset)
        if len(shape) != 2 or len(data) != shape[0] * shape[1]:
            raise RuntimeError(f"bad HDF5 dataset {path}:{dataset}")
        return [data[i * shape[1]:(i + 1) * shape[1]] for i in range(shape[0])]


def c1ke(d: Path) -> list[dict[str, float]]:
    out = []
    for line in (d / "C1ke").read_text().splitlines():
        if line.strip():
            out.append(dict(zip(C1KE_COLS, [float(x) for x in line.split()])))
    return out


def profile_metrics(h5: H5, d: Path, i: int) -> dict[str, float]:
    path = d / f"time_{i:03d}.h5"
    elems = h5.matrix(path, "/mesh/elements")
    jphi = [r[0] for r in h5.matrix(path, "/fields/jphi")]
    rows = []
    for e, j in zip(elems, jphi):
        r, z, w = e[4], e[5], max(e[2], 0.0)
        if abs(r - R_CENTER) <= R_BAND:
            rows.append((r, z, w, j, abs(j)))
    if not rows:
        raise RuntimeError("empty sheet ROI")
    absint = sum(a * w for _, _, w, _, a in rows)
    peak = max(rows, key=lambda x: x[4])
    centroid = sum(z * a * w for _, z, w, _, a in rows) / max(absint, 1e-300)
    var = sum((z-centroid)**2 * a * w for _, z, w, _, a in rows) / max(absint, 1e-300)
    center = sum(a*w for _, z, w, _, a in rows if abs(z-Z_CENTER) <= CENTER_HW)
    shoulder = sum(a*w for _, z, w, _, a in rows if abs(abs(z-Z_CENTER)-Z_SHOULDER) <= SHOULDER_HW)
    cut = HIGH_J_FRACTION * peak[4]
    high = sum(a*w for _, _, w, _, a in rows if a >= cut)
    return {
        "Jpk": peak[4],
        "W_sheet": 2.354820045 * math.sqrt(max(var, 0.0)),
        "Jint_abs": absint,
        "Jint_high": high,
        "center_abs_current": center,
        "shoulder_abs_current": shoulder,
        "center_to_shoulder_ratio": center / max(shoulder, 1e-300),
    }


def extract(d: Path) -> list[dict[str, float]]:
    h5 = H5()
    flux = h5.data(d / "C1.h5", "/scalars/Reconnected_Flux")
    out = []
    for i, k in enumerate(c1ke(d)):
        if not (d / f"time_{i:03d}.h5").exists():
            break
        row = {
            "index": i,
            "time": k["time"],
            "kinetic_energy": k["ekin"],
            "magnetic_energy": k["emagp"] + k["emagt"] + k["emag3"],
            "total_energy": k["etot"],
            "Reconnected_Flux": flux[i] if i < len(flux) else math.nan,
        }
        row.update(profile_metrics(h5, d, i))
        out.append(row)
    for i, row in enumerate(out):
        a = out[max(i-1, 0)]
        b = out[min(i+1, len(out)-1)]
        dt = b["time"] - a["time"]
        row["reconnection_rate"] = (b["Reconnected_Flux"] - a["Reconnected_Flux"]) / dt if dt else 0.0
    return out


def pct(c: float, b: float) -> float:
    return 100.0 * (c / b - 1.0) if abs(b) > 1e-300 else math.nan


def trapz(rows: list[dict[str, float]], key: str, t0: float, t1: float) -> float:
    selected = [x for x in rows if t0 <= x["time"] <= t1]
    total = 0.0
    for a, b in zip(selected, selected[1:]):
        total += 0.5 * (a[key] + b[key]) * (b["time"] - a["time"])
    return total


def compare_case(name: str, base: list[dict[str, float]], ctrl: list[dict[str, float]]) -> tuple[dict, list[dict]]:
    rows = []
    for b, c in zip(base, ctrl):
        rows.append({
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
    active = [r for r in rows if 0.05 <= r["time"] <= TRAIN_END]
    mean_width = sum(r["width_gain_pct"] for r in active) / len(active)
    min_width = min(r["width_gain_pct"] for r in active)
    positive_fraction = sum(r["width_gain_pct"] > 0 for r in active) / len(active)
    max_jpk = max(r["Jpk_change_pct"] for r in active)
    mean_jpk = sum(r["Jpk_change_pct"] for r in active) / len(active)

    base_high = trapz(base, "Jint_high", 0.05, TRAIN_END)
    ctrl_high = trapz(ctrl, "Jint_high", 0.05, TRAIN_END)
    int_high_pct = pct(ctrl_high, base_high)
    base_reconn = max(abs(r["reconnection_rate"]) for r in base if 0.05 <= r["time"] <= TRAIN_END)
    ctrl_reconn = max(abs(r["reconnection_rate"]) for r in ctrl if 0.05 <= r["time"] <= TRAIN_END)
    peak_reconn_pct = pct(ctrl_reconn, base_reconn)

    width_ok = mean_width > WIDTH_GAIN_THRESHOLD_PCT and positive_fraction >= POSITIVE_WIDTH_FRACTION_THRESHOLD
    j_ok = int_high_pct < HIGH_J_IMPROVEMENT_THRESHOLD_PCT and max_jpk <= JPK_WORSENING_TOLERANCE_PCT

    if width_ok and j_ok:
        cls = "M3DC1_MAGNETIC_PULSE_TRAIN_SUSTAINED_CONTROL"
    elif width_ok:
        cls = "M3DC1_MAGNETIC_PULSE_TRAIN_WIDTH_ONLY"
    elif int_high_pct > JPK_WORSENING_TOLERANCE_PCT or max_jpk > JPK_WORSENING_TOLERANCE_PCT:
        cls = "M3DC1_MAGNETIC_PULSE_TRAIN_J_WORSE"
    elif int_high_pct < HIGH_J_IMPROVEMENT_THRESHOLD_PCT:
        cls = "M3DC1_MAGNETIC_PULSE_TRAIN_CURRENT_ONLY"
    else:
        cls = "M3DC1_MAGNETIC_PULSE_TRAIN_NO_SUSTAINED_CONTROL"

    return {
        "case": name,
        "classification": cls,
        "mean_width_gain_pct": mean_width,
        "min_width_gain_pct": min_width,
        "positive_width_fraction": positive_fraction,
        "mean_Jpk_change_pct": mean_jpk,
        "max_Jpk_change_pct": max_jpk,
        "integrated_high_J_change_pct": int_high_pct,
        "peak_abs_reconnection_rate_change_pct": peak_reconn_pct,
        "final_delta_Reconnected_Flux": rows[-1]["delta_Reconnected_Flux"],
        "max_abs_delta_magnetic_energy": max(abs(r["delta_magnetic_energy"]) for r in active),
        "width_gate_pass": width_ok,
        "current_gate_pass": j_ok,
    }, rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def copy_compact(d: Path, prefix: str) -> None:
    for name in ["C1input", "C1ke", "run_status.txt", "launcher.stderr", "launch_command.sh", "elapsed_seconds.txt"]:
        p = d / name
        if p.exists():
            shutil.copy2(p, OUT / f"{prefix}_{name}")


def save_provenance() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = {
        "frozen_before_outcomes": True,
        "amp": AMP,
        "dt": DT,
        "ntimemax": NTIMEMAX,
        "train_start": TRAIN_START,
        "train_end": TRAIN_END,
        "ramp": RAMP,
        "cases": CASES,
        "gates": {
            "mean_width_gain_pct_gt": WIDTH_GAIN_THRESHOLD_PCT,
            "positive_width_fraction_ge": POSITIVE_WIDTH_FRACTION_THRESHOLD,
            "integrated_high_J_change_pct_lt": HIGH_J_IMPROVEMENT_THRESHOLD_PCT,
            "max_Jpk_worsening_pct_le": JPK_WORSENING_TOLERANCE_PCT,
        },
        "scientific_note": "Amplitude is fixed at the previously validated short-pulse value; only period and on-time are varied.",
    }
    (OUT / "pulse_train_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (OUT / "runtime_provenance.txt").write_text(
        f"repo={REPO}\nsource={SRC}\nbaseline={BASE}\nexecutable={EXE}\n"
        f"executable_sha256={sha256_file(EXE) if EXE.exists() else 'missing'}\nrun_root={RUN_ROOT}\n"
    )
    diff = sh(["git", "diff", "--", "unstructured/M3Dmodules.f90", "unstructured/input.f90", "unstructured/ludef_t.f90"], cwd=SRC)
    (OUT / "m3dc1_pulse_train_source.diff").write_text(diff.stdout)


def summarize(base_dir: Path, zero_dir: Path, case_dirs: dict[str, Path]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = extract(base_dir)
    zero = extract(zero_dir)
    write_csv(OUT / "baseline_timeseries.csv", base)

    max_zero = 0.0
    for b, z in zip(base, zero):
        for key in ["W_sheet", "Jpk", "Jint_high", "Reconnected_Flux", "magnetic_energy"]:
            max_zero = max(max_zero, abs(z[key] - b[key]))
    zero_summary = {"max_abs_metric_delta": max_zero, "tolerance": ZERO_ABS_TOL, "pass": max_zero <= ZERO_ABS_TOL}
    (OUT / "zero_equivalence.json").write_text(json.dumps(zero_summary, indent=2) + "\n")
    if not zero_summary["pass"]:
        raise RuntimeError(f"zero equivalence failed: {zero_summary}")

    summaries = []
    for spec in CASES:
        name = spec["name"]
        ctrl = extract(case_dirs[name])
        summary, deltas = compare_case(name, base, ctrl)
        summary.update({
            "period": spec["period"],
            "pulse_width": spec["pulse_width"],
            "duty_cycle": (spec["pulse_width"] / spec["period"]) if spec["period"] > 0 else None,
        })
        summaries.append(summary)
        write_csv(OUT / f"{name}_deltas.csv", deltas)
        copy_compact(case_dirs[name], name)

    write_csv(OUT / "pulse_train_matrix.csv", summaries)
    viable = [s for s in summaries if s["classification"] == "M3DC1_MAGNETIC_PULSE_TRAIN_SUSTAINED_CONTROL"]
    best = None
    if viable:
        best = max(viable, key=lambda s: (s["mean_width_gain_pct"], -s["integrated_high_J_change_pct"], -s["max_Jpk_change_pct"]))
    overall = {
        "classification": "M3DC1_MAGNETIC_PULSE_TRAIN_SUSTAINED_CONTROL_FOUND" if viable else "M3DC1_MAGNETIC_PULSE_TRAIN_NO_FULL_SUSTAINED_CONTROL_FOUND",
        "zero_equivalence": zero_summary,
        "best_full_control_case": best,
        "cases": summaries,
        "claim_boundary": "Native normalized GEM magnetic pulse-train audit only; no lithium dimensional transfer, reactor stabilization, or experimental TCT validation is implied.",
    }
    (OUT / "pulse_train_summary.json").write_text(json.dumps(overall, indent=2) + "\n")

    lines = [
        "# M3D-C1 Magnetic Pulse-Train Audit", "",
        f"Primary classification: `{overall['classification']}`", "",
        "## Frozen design", "",
        f"- amplitude: `{AMP}`", f"- dt: `{DT}`",
        f"- train window: `{TRAIN_START} <= t < {TRAIN_END}`",
        "- amplitude was not tuned; only pulse period/on-time were varied.", "",
        "## Results", "",
    ]
    for s in summaries:
        lines.append(
            f"- `{s['case']}`: `{s['classification']}`; mean width {s['mean_width_gain_pct']:.6g}%, "
            f"positive-width fraction {s['positive_width_fraction']:.3f}, max Jpk {s['max_Jpk_change_pct']:.6g}%, "
            f"integrated high-J {s['integrated_high_J_change_pct']:.6g}%."
        )
    lines += [
        "", "## Interpretation gate", "",
        "A pulse train counts as sustained control only if it maintains a positive mean sheet-width gain for most of the active window while also reducing integrated high-|J| loading without exceeding the predeclared peak-J worsening tolerance.",
        "", "## Claim boundary", "", overall["claim_boundary"], "",
    ]
    (OUT / "M3DC1_MAGNETIC_PULSE_TRAIN_REPORT.md").write_text("\n".join(lines))


def run_all() -> None:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    base = prepare_baseline()
    zero = prepare_dir("zero_train", 0.0, 0.05, 0.02, TRAIN_END)
    case_dirs = {c["name"]: prepare_dir(c["name"], AMP, c["period"], c["pulse_width"], c["t_off"]) for c in CASES}

    for d in [base, zero, *case_dirs.values()]:
        print(f"[pulse-train] running {d.name}", flush=True)
        execute(d)

    summarize(base, zero, case_dirs)
    save_provenance()
    copy_compact(base, "baseline")
    copy_compact(zero, "zero_train")
    print(f"[pulse-train] complete: {OUT}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Native M3D-C1 fixed-amplitude magnetic pulse-train audit")
    ap.add_argument("action", choices=["install", "build", "run", "all"])
    args = ap.parse_args()
    if args.action in ("install", "all"):
        changed = install_operator()
        print(f"[pulse-train] operator patch {'installed' if changed else 'already present'}")
    if args.action in ("build", "all"):
        build()
        print(f"[pulse-train] build ok: {EXE}")
    if args.action in ("run", "all"):
        run_all()


if __name__ == "__main__":
    main()
