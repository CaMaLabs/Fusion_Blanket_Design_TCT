from __future__ import annotations

import math
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


C1KE_COLS = [
    "ntime", "time", "ekin", "gamma_gr", "ekinp", "ekint",
    "ekin3", "emagp", "emagt", "emag3", "etot",
]


def _nums(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?|[-+]?\.\d+(?:[Ee][-+]?\d+)?", text)]


class H5Dump:
    def __init__(self, configured: str = "") -> None:
        path = configured.strip() if configured else ""
        self.exe = path or shutil.which("h5dump") or ""
        if not self.exe:
            raise RuntimeError("h5dump not found; activate the M3D-C1 Spack environment or set paths.h5dump")

    def run(self, args: list[str]) -> str:
        p = subprocess.run([self.exe, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode:
            raise RuntimeError(p.stdout[-4000:])
        return p.stdout

    def data(self, path: Path, dataset: str) -> list[float]:
        text = self.run(["-y", "-w", "0", "-d", dataset, str(path)])
        match = re.search(r"DATA \{(.*?)\}\s*\}\s*\}", text, re.S)
        return _nums(match.group(1)) if match else []

    def shape(self, path: Path, dataset: str) -> tuple[int, ...]:
        text = self.run(["-H", "-d", dataset, str(path)])
        match = re.search(r"DATASPACE\s+SIMPLE\s+\{\s*\(\s*([0-9, ]+)\)", text)
        if not match:
            return ()
        return tuple(int(x.strip()) for x in match.group(1).split(","))

    def matrix(self, path: Path, dataset: str) -> list[list[float]]:
        shape = self.shape(path, dataset)
        data = self.data(path, dataset)
        if len(shape) != 2 or len(data) != shape[0] * shape[1]:
            raise RuntimeError(f"bad dataset {path}:{dataset}, shape={shape}, values={len(data)}")
        return [data[i * shape[1]:(i + 1) * shape[1]] for i in range(shape[0])]


def read_c1ke(run_dir: Path) -> list[dict[str, float]]:
    path = run_dir / "C1ke"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values = [float(x) for x in line.split()]
            rows.append(dict(zip(C1KE_COLS, values)))
    return rows


def scalar_series(h5: H5Dump, run_dir: Path, name: str) -> list[float]:
    path = run_dir / "C1.h5"
    if not path.exists():
        return []
    try:
        return h5.data(path, f"/scalars/{name}")
    except Exception:
        return []


def _profile_metrics(h5: H5Dump, run_dir: Path, index: int, cfg: dict[str, Any]) -> dict[str, float]:
    path = run_dir / f"time_{index:03d}.h5"
    elems = h5.matrix(path, "/mesh/elements")
    jphi = [row[0] for row in h5.matrix(path, "/fields/jphi")]
    psi = [row[0] for row in h5.matrix(path, "/fields/psi")]
    ex = cfg["extractor"]
    rows: list[dict[str, float]] = []
    for element, jj, pp in zip(elems, jphi, psi):
        r, z, weight = element[4], element[5], max(element[2], 0.0)
        if abs(r - float(ex["r_center"])) <= float(ex["r_band"]):
            rows.append({"R": r, "Z": z, "w": weight, "j": jj, "aj": abs(jj), "psi": pp})
    if not rows:
        raise RuntimeError(f"empty sheet ROI in {path}")
    rows.sort(key=lambda x: x["Z"])
    absint = sum(r["aj"] * r["w"] for r in rows)
    signed = sum(r["j"] * r["w"] for r in rows)
    peak = max(rows, key=lambda r: r["aj"])
    centroid = sum(r["Z"] * r["aj"] * r["w"] for r in rows) / max(absint, 1e-300)
    variance = sum((r["Z"] - centroid) ** 2 * r["aj"] * r["w"] for r in rows) / max(absint, 1e-300)
    center = sum(r["aj"] * r["w"] for r in rows if abs(r["Z"] - float(ex["z_center"])) <= float(ex["center_halfwidth"]))
    shoulder = sum(r["aj"] * r["w"] for r in rows if abs(abs(r["Z"] - float(ex["z_center"])) - float(ex["z_shoulder"])) <= float(ex["shoulder_halfwidth"]))
    high_cut = float(ex["high_j_fraction"]) * peak["aj"]
    high_loading = sum(r["aj"] * r["w"] for r in rows if r["aj"] >= high_cut)
    psi_values = [r["psi"] for r in rows]
    dz = rows[-1]["Z"] - rows[0]["Z"]
    bz_proxy = (rows[-1]["psi"] - rows[0]["psi"]) / dz if dz else 0.0
    return {"Jpk": peak["aj"], "Jpk_R": peak["R"], "Jpk_Z": peak["Z"], "Jint_abs": absint, "Jint_signed": signed, "Jint_high": high_loading, "W_sheet": 2.354820045 * math.sqrt(max(variance, 0.0)), "current_centroid_Z": centroid, "center_abs_current": center, "shoulder_abs_current": shoulder, "center_to_shoulder_ratio": center / max(shoulder, 1e-300), "roi_psi_span": max(psi_values) - min(psi_values), "roi_Bz_proxy_dpsi_dZ": bz_proxy}


def extract_series(run_dir: str | Path, cfg: dict[str, Any]) -> list[dict[str, float]]:
    run_dir = Path(run_dir)
    h5 = H5Dump(cfg["paths"].get("h5dump", ""))
    c1 = read_c1ke(run_dir)
    recon = scalar_series(h5, run_dir, "Reconnected_Flux")
    tor_current = scalar_series(h5, run_dir, "toroidal_current")
    loop_voltage = scalar_series(h5, run_dir, "loop_voltage")
    rows: list[dict[str, float]] = []
    for i, energy in enumerate(c1):
        time_file = run_dir / f"time_{i:03d}.h5"
        if not time_file.exists():
            break
        row = {"index": float(i), "time": float(energy["time"]), "kinetic_energy": float(energy["ekin"]), "magnetic_energy": float(energy["emagp"] + energy["emagt"] + energy["emag3"]), "total_energy": float(energy["etot"]), "Reconnected_Flux": recon[i] if i < len(recon) else math.nan, "toroidal_current": tor_current[i] if i < len(tor_current) else math.nan, "loop_voltage": loop_voltage[i] if i < len(loop_voltage) else math.nan}
        row.update(_profile_metrics(h5, run_dir, i, cfg))
        rows.append(row)
    if not rows:
        raise RuntimeError(f"no extractable field outputs in {run_dir}")
    return rows


def _pct(new: float, base: float) -> float:
    if not math.isfinite(new) or not math.isfinite(base) or abs(base) < 1e-300:
        return math.nan
    return 100.0 * (new / base - 1.0)


def compare_series(baseline: list[dict[str, float]], controlled: list[dict[str, float]], active_start: float, active_end: float) -> dict[str, float]:
    count = min(len(baseline), len(controlled))
    pairs = list(zip(baseline[:count], controlled[:count]))
    active = [(b, c) for b, c in pairs if active_start <= c["time"] <= active_end] or pairs[-1:]
    width_gains = [_pct(c["W_sheet"], b["W_sheet"]) for b, c in active]
    j_changes = [_pct(c["Jpk"], b["Jpk"]) for b, c in active]
    high_changes = [_pct(c["Jint_high"], b["Jint_high"]) for b, c in active]
    magnetic_changes = [_pct(c["magnetic_energy"], b["magnetic_energy"]) for b, c in active]
    current_changes = [abs(_pct(c["toroidal_current"], b["toroidal_current"])) for b, c in active if math.isfinite(c["toroidal_current"]) and math.isfinite(b["toroidal_current"]) and abs(b["toroidal_current"]) > 1e-300]
    final_b, final_c = pairs[-1]
    def recon_rate(series):
        best = 0.0
        for a, b in zip(series, series[1:]):
            dt = b["time"] - a["time"]
            if dt and math.isfinite(a["Reconnected_Flux"]) and math.isfinite(b["Reconnected_Flux"]):
                best = max(best, abs((b["Reconnected_Flux"] - a["Reconnected_Flux"]) / dt))
        return best
    return {"mean_active_width_gain_pct": sum(width_gains) / len(width_gains), "min_active_width_gain_pct": min(width_gains), "max_active_width_gain_pct": max(width_gains), "max_active_peak_j_change_pct": max(j_changes), "mean_active_peak_j_change_pct": sum(j_changes) / len(j_changes), "mean_active_high_j_change_pct": sum(high_changes) / len(high_changes), "max_abs_magnetic_energy_change_pct": max(abs(x) for x in magnetic_changes), "max_abs_toroidal_current_change_pct": max(current_changes) if current_changes else math.nan, "final_reconnected_flux_change_pct": _pct(final_c["Reconnected_Flux"], final_b["Reconnected_Flux"]), "peak_reconnection_rate_change_pct": _pct(recon_rate(controlled[:count]), recon_rate(baseline[:count])), "final_center_to_shoulder_change_pct": _pct(final_c["center_to_shoulder_ratio"], final_b["center_to_shoulder_ratio"]), "final_psi_span_delta": final_c["roi_psi_span"] - final_b["roi_psi_span"], "final_bz_proxy_delta": final_c["roi_Bz_proxy_dpsi_dZ"] - final_b["roi_Bz_proxy_dpsi_dZ"]}
