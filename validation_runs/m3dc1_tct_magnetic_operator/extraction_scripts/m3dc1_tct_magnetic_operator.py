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
OUT = REPO / "validation_runs/m3dc1_tct_magnetic_operator"
SRC = Path("/home/ubuntu/M3DC1-official")
RUN_ROOT = Path("/home/ubuntu/m3dc1_runs")
BASE = RUN_ROOT / "TCT_MECHANISM_BASELINE"
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
H5DUMP = Path("/home/ubuntu/spack/opt/spack/linux-skylake/hdf5-1.14.6-uoyar6dpmk3uncnm7a5mogs4losjyziw/bin/h5dump")
COLS = ["ntime","time","ekin","gamma_gr","ekinp","ekint","ekin3","emagp","emagt","emag3","etot"]
SCALARS = ["time","Reconnected_Flux","psi0","psi_lcfs","psimin","xmag","zmag","xnull","znull","toroidal_current","toroidal_flux","volume","loop_voltage"]
R_CENTER = 10.0
R_BAND = 0.25
Z_CENTER = 1.0
Z_SHOULDER = 0.561
OPERATOR = {
    "imag_control": 1,
    "mag_ctrl_r0": 10.0,
    "mag_ctrl_z0": 1.0,
    "mag_ctrl_wr": 0.5,
    "mag_ctrl_wz": 0.5,
    "mag_ctrl_t_on": 0.0,
    "mag_ctrl_t_ramp": 0.0,
    "mag_ctrl_t_off": 0.05,
}
MATRIX = [("zero", 0.0), ("plus", 0.01), ("minus", -0.01)]
SUSTAINED = ("sustained_minus", -0.01, 0.0, 0.25)
MU0 = 4.0e-7 * math.pi
REFERENCE_LITHIUM = {
    "background_B_T": 7.2,
    "lithium_velocity_km_s": 0.0022,
    "lithium_layer_thickness_m": 0.0014,
    "trench_width_mm": 10.0,
    "wetted": True,
    "source": "WINNING_CONFIGURATION_SUMMARY.md Candidate-0 values",
}


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
    out = []
    for line in (run_dir / "C1ke").read_text().splitlines():
        if line.strip():
            out.append(dict(zip(COLS, [float(x) for x in line.split()])))
    return out


def status(run_dir: Path) -> str:
    p = run_dir / "run_status.txt"
    return p.read_text().strip() if p.exists() else "missing"


def replace_or_add(text: str, key: str, value: str) -> str:
    pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if pat.search(text):
        return pat.sub(rf"\g<1>{value}", text)
    return text.replace("\n /\n", f"\n {key} = {value}\n /\n")


def prepare_run(name: str, amp: float) -> Path:
    run_dir = RUN_ROOT / f"TCT_MAGOP_{name.upper()}"
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
    text = replace_or_add(text, "ntimemax", "2")
    text = replace_or_add(text, "ntimepr", "1")
    for key, val in OPERATOR.items():
        text = replace_or_add(text, key, str(val))
    text = replace_or_add(text, "mag_ctrl_amp", f"{amp:.10g}")
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
    return run_dir


def prepare_custom_run(name: str, amp: float, t_on: float, t_off: float, ntimemax: int) -> Path:
    run_dir = prepare_run(name, amp)
    text = (run_dir / "C1input").read_text()
    text = replace_or_add(text, "ntimemax", str(ntimemax))
    text = replace_or_add(text, "mag_ctrl_t_on", str(t_on))
    text = replace_or_add(text, "mag_ctrl_t_off", str(t_off))
    (run_dir / "C1input").write_text(text)
    return run_dir


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


def metrics(run_dir: Path, t: int) -> dict[str, float]:
    rows = profile(run_dir, t)
    absint = sum(r["abs_jphi"] * r["weight"] for r in rows)
    signed = sum(r["jphi"] * r["weight"] for r in rows)
    mean = sum(r["Z"] * r["abs_jphi"] * r["weight"] for r in rows) / max(absint, 1e-300)
    var = sum((r["Z"] - mean) ** 2 * r["abs_jphi"] * r["weight"] for r in rows) / max(absint, 1e-300)
    peak = max(rows, key=lambda r: r["abs_jphi"])
    center = sum(r["abs_jphi"] * r["weight"] for r in rows if abs(r["Z"] - Z_CENTER) <= 0.2805)
    shoulder = sum(r["abs_jphi"] * r["weight"] for r in rows if abs(abs(r["Z"] - Z_CENTER) - Z_SHOULDER) <= 0.2805)
    psi_vals = [r["psi"] for r in rows]
    # ROI finite-difference proxy for reconnecting in-plane field component dpsi/dZ.
    bz_proxy = 0.0
    if len(rows) >= 2:
        denom = rows[-1]["Z"] - rows[0]["Z"]
        if denom != 0:
            bz_proxy = (rows[-1]["psi"] - rows[0]["psi"]) / denom
    return {
        "Jpk": peak["abs_jphi"],
        "Jpk_R": peak["R"],
        "Jpk_Z": peak["Z"],
        "Jint_abs": absint,
        "Jint_signed": signed,
        "W_fwhm_equiv": 2.354820045 * math.sqrt(max(var, 0.0)),
        "current_centroid_Z": mean,
        "center_abs_current": center,
        "shoulder_abs_current": shoulder,
        "center_to_shoulder_ratio": center / max(shoulder, 1e-300),
        "roi_psi_min": min(psi_vals),
        "roi_psi_max": max(psi_vals),
        "roi_psi_span": max(psi_vals) - min(psi_vals),
        "roi_Bz_proxy_dpsi_dZ": bz_proxy,
    }


def scalars(run_dir: Path) -> dict[str, list[float]]:
    return {s: h5data(run_dir / "C1.h5", f"/scalars/{s}") for s in SCALARS}


def series(run_dir: Path) -> list[dict[str, float]]:
    sc = scalars(run_dir)
    rows = []
    for i, k in enumerate(c1ke(run_dir)):
        row = {"ntime": int(k["ntime"]), "time": k["time"], "kinetic_energy": k["ekin"], "magnetic_energy": k["emagp"] + k["emagt"] + k["emag3"], "total_energy": k["etot"]}
        row.update(metrics(run_dir, i))
        for s, v in sc.items():
            row[s] = v[i] if i < len(v) else math.nan
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def copy_compact(run_dir: Path, prefix: str) -> None:
    for f in ["C1input", "C1ke", "run_status.txt", "launcher.stderr", "launch_command.sh"]:
        if (run_dir / f).exists():
            shutil.copy2(run_dir / f, OUT / f"{prefix}_{f}")
    if (run_dir / "C1stdout").exists():
        keep = [ln for ln in (run_dir / "C1stdout").read_text(errors="replace").splitlines() if re.search(r"WARNING|Warning|ERROR|Error|mesh entity counts|magnetic axis|X-point|Poloidal flux|Total energy|Toroidal current|Toroidal flux|Volume|TIME STEP|Stopped at|Done time loop", ln)]
        (OUT / f"compact_{prefix}_stdout.log").write_text("\n".join(keep) + "\n")


def summarize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = series(BASE)[:3]
    write_csv(OUT / "baseline_short_timeseries.csv", base)
    summaries = []
    for name, amp in MATRIX:
        d = RUN_ROOT / f"TCT_MAGOP_{name.upper()}"
        if not (d / "C1ke").exists():
            continue
        s = series(d)
        write_csv(OUT / f"{name}_timeseries.csv", s)
        copy_compact(d, name)
        deltas = []
        for b, r in zip(base, s):
            row = {"case": name, "mag_ctrl_amp": amp, "time": r["time"]}
            for key in ["roi_psi_span","roi_Bz_proxy_dpsi_dZ","Jpk","W_fwhm_equiv","center_abs_current","shoulder_abs_current","Jint_abs","Reconnected_Flux","magnetic_energy","toroidal_current"]:
                row[f"delta_{key}"] = r[key] - b[key]
                row[f"d_{key}_dA"] = 0.0 if amp == 0.0 else (r[key] - b[key]) / amp
            deltas.append(row)
        write_csv(OUT / f"{name}_deltas.csv", deltas)
        final = deltas[-1]
        summaries.append({
            "case": name,
            "mag_ctrl_amp": amp,
            "run_status": status(d),
            "max_abs_delta_psi_span": max(abs(x["delta_roi_psi_span"]) for x in deltas),
            "max_abs_delta_Bz_proxy": max(abs(x["delta_roi_Bz_proxy_dpsi_dZ"]) for x in deltas),
            "final_dW_dA": final["d_W_fwhm_equiv_dA"],
            "final_dJpk_dA": final["d_Jpk_dA"],
            "final_dJcenter_dA": final["d_center_abs_current_dA"],
            "final_dJshoulder_dA": final["d_shoulder_abs_current_dA"],
            "final_dReconnectedFlux_dA": final["d_Reconnected_Flux_dA"],
            "final_dMagneticEnergy_dA": final["d_magnetic_energy_dA"],
            "final_delta_W": final["delta_W_fwhm_equiv"],
            "final_delta_Jpk": final["delta_Jpk"],
            "final_delta_Jcenter": final["delta_center_abs_current"],
            "final_delta_Jshoulder": final["delta_shoulder_abs_current"],
        })
    if summaries:
        write_csv(OUT / "magnetic_operator_transfer_matrix.csv", summaries)
        nonzero = [x for x in summaries if x["mag_ctrl_amp"] != 0.0]
        reachable = any(x["max_abs_delta_psi_span"] > 1e-10 or x["max_abs_delta_Bz_proxy"] > 1e-10 for x in nonzero)
        authority = any(x["final_delta_W"] > 1e-6 and x["final_delta_Jpk"] < -1e-6 for x in nonzero)
        selected = next((x["case"] for x in nonzero if x["final_delta_W"] > 1e-6 and x["final_delta_Jpk"] < -1e-6), None)
        cls = "M3DC1_MAGNETIC_OPERATOR_SHEET_AUTHORITY_PASS" if authority else ("M3DC1_MAGNETIC_OPERATOR_NO_SHEET_AUTHORITY" if reachable else "NATIVE_MAGNETIC_OPERATOR_INACTIVE_OR_UNREACHABLE")
        (OUT / "magnetic_operator_transfer_summary.json").write_text(json.dumps({
            "classification": cls,
            "operator": "localized flux/vector-potential source in flux_nolin",
            "predeclared_matrix": MATRIX,
            "operator_definition": OPERATOR,
            "reachable_field_level": reachable,
            "sheet_authority_gate_pass": authority,
            "selected_transfer_sign": selected,
            "cases": summaries,
            "lithium_bridge": "requires dimensional magnetic calibration before Ruzic/Fiflis evaluation" if authority else "not evaluated unless sheet-authority gate passes",
        }, indent=2) + "\n")
    sustained_dir = RUN_ROOT / f"TCT_MAGOP_{SUSTAINED[0].upper()}"
    if (sustained_dir / "C1ke").exists():
        sustained = series(sustained_dir)
        write_csv(OUT / "sustained_minus_timeseries.csv", sustained)
        copy_compact(sustained_dir, "sustained_minus")
        rows = []
        for b, r in zip(series(BASE), sustained):
            rows.append({
                "time": r["time"],
                "delta_W_fwhm_equiv": r["W_fwhm_equiv"] - b["W_fwhm_equiv"],
                "width_gain_pct": 100.0 * (r["W_fwhm_equiv"] - b["W_fwhm_equiv"]) / b["W_fwhm_equiv"],
                "delta_Jpk": r["Jpk"] - b["Jpk"],
                "Jpk_change_pct": 100.0 * (r["Jpk"] - b["Jpk"]) / b["Jpk"],
                "delta_center_abs_current": r["center_abs_current"] - b["center_abs_current"],
                "delta_shoulder_abs_current": r["shoulder_abs_current"] - b["shoulder_abs_current"],
                "delta_Jint_abs": r["Jint_abs"] - b["Jint_abs"],
                "delta_Reconnected_Flux": r["Reconnected_Flux"] - b["Reconnected_Flux"],
                "delta_magnetic_energy": r["magnetic_energy"] - b["magnetic_energy"],
            })
        write_csv(OUT / "sustained_minus_deltas.csv", rows)
        active = [r for r in rows if 0.0 <= r["time"] <= 0.25]
        sustained_pass = sum(r["width_gain_pct"] for r in active) / len(active) > 0.05 and max(r["Jpk_change_pct"] for r in active) <= 0.0
        (OUT / "magnetic_operator_sustained_summary.json").write_text(json.dumps({
            "classification": "M3DC1_MAGNETIC_OPERATOR_SUSTAINED_SHEET_CONTROL" if sustained_pass else "M3DC1_MAGNETIC_OPERATOR_FAILS_SUSTAINED_CONTROL",
            "case": SUSTAINED[0],
            "mag_ctrl_amp": SUSTAINED[1],
            "active_window": [SUSTAINED[2], SUSTAINED[3]],
            "mean_active_width_gain_pct": sum(r["width_gain_pct"] for r in active) / len(active),
            "min_active_width_gain_pct": min(r["width_gain_pct"] for r in active),
            "max_active_Jpk_change_pct": max(r["Jpk_change_pct"] for r in active),
            "final_reconnected_flux_delta": rows[-1]["delta_Reconnected_Flux"],
            "final_magnetic_energy_delta": rows[-1]["delta_magnetic_energy"],
        }, indent=2) + "\n")
    patch = run(["git", "diff", "--", "unstructured/M3Dmodules.f90", "unstructured/input.f90", "unstructured/ludef_t.f90"], cwd=SRC)
    (OUT / "native_magnetic_operator_patch.diff").write_text(patch)


def write_inventory() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "native_magnetic_operator_inventory.md").write_text("""# Native M3D-C1 Magnetic Operator Inventory

Scope: nonlinear GEM current-sheet control. Earlier global `scale_ext_field`, GEM `eps`, and `icd_source` actuator tests are not repeated.

## Candidate Inventory

| Candidate | Source/routine | Equation affected | Evolution or initialization | Localization | Temporal modulation | Sign/amplitude | GEM reachability | Boundary/volume | Default off | Expected sheet relation | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RMP/error external field | `unstructured/rmp.f90`, `rmp_per`, `calculate_external_fields`, `rmp_field` | Builds `psi_ext`, `bz_ext`, `bf_ext`, `bfp_ext`; nonlinear terms use `psx79`, `bzx79`, `bfpx79` when `use_external_fields` and subtract flags are active | Field is loaded/calculated at initialization/restart, not dynamically commanded each timestep in this GEM setup | File/coil defined; possible with external data but not simple local GEM ROI command | No native time gate found for nonlinear GEM evolution | `scale_ext_field`, shifts, coil currents | Previous global `scale_ext_field` showed no current-loading response; machinery not exhausted but no simple dynamic local control path | Volume external/vacuum fields | yes | Could alter Lorentz/VxB terms if reachable | Candidate, but not first transfer-function target |
| PF/vacuum coil field | `unstructured/gradshafranov.f90`, `pf_coil_field`, `vacuum_field`; `unstructured/coils.f90`, `field_from_coils` | Equilibrium/vacuum coil `psi_coil_field` and optional subtraction | Primarily equilibrium/Grad-Shafranov initialization; feedback routine exists inside GS iteration | Coil geometry localized by files, not local GEM sheet operator | Feedback inside GS solve, not the nonlinear GEM time loop | coil/current files and GS feedback gains | Not a clean nonlinear GEM control actuator without invasive setup | Boundary/vacuum coil field | yes | Interpretable surface-current relation, but reachability in GEM time evolution uncertain | Candidate for later physical mapping |
| GS coil feedback | `unstructured/gradshafranov.f90`, `coil_feedback` | Updates `psi_coil_field` from axis/X-point error during GS solve | Iterative equilibrium feedback, not nonlinear GEM controller | Coil file geometry | Dynamic within GS iteration only | feedback arrays | Does not directly provide current-sheet transfer-function in nonlinear GEM run | Boundary/vacuum coil field | yes | Controls axis/X-point equilibrium, not local sheet width directly | Not selected for this rung |
| Loop voltage | `unstructured/ludef_t.f90`, `flux_nolin`; `unstructured/model.f90`, `boundary_mag` | Adds global flux/induction term | During evolution | Global only | `vloop`, frequency | sign and amplitude | Reaches flux equation but not local field shaping | Global volume/boundary induction | yes | Changes global current/flux, not local sheet redistribution | Rejected for local sheet-control gate |
| Native current drive | `unstructured/transport.f90`, `cd_func`; `unstructured/ludef_t.f90`, `flux_nolin` | Flux equation through eta/current-drive term | During evolution | Local Gaussian/profile | time gate added in previous rung | sign and amplitude | Proven reachable but insufficient sheet-width authority | Volume current-drive | yes | Current redistribution attempted; no width authority | Do not escalate |
| Localized magnetic flux/vector-potential source | `unstructured/ludef_t.f90`, `flux_nolin` plus input/module additions | Direct source in native flux/vector-potential equation | During nonlinear evolution | Gaussian in fixed GEM ROI | explicit on/ramp/off gate | sign and amplitude | Designed as plasma-side operator reachability probe | Local volume magnetic/induction operator, proxy for boundary-field control | yes | Should directly perturb `psi`, derived reconnecting field, and possibly `jphi`/width | Selected for transfer-function audit |

## Selection Rationale

The preferred native boundary-field route is not cleanly time-commandable in the existing nonlinear GEM setup without larger RMP/external-field plumbing. The selected transfer-function operator is therefore a minimal custom magnetic operator in the existing flux equation. It is used only to answer whether a local magnetic/vector-potential perturbation can move the GEM sheet in the desired direction.
""")


def ruzic_row(delta_b_t: float, angle_deg: float) -> dict[str, float | str | bool]:
    sys.path.insert(0, str(REPO))
    from liquid_lithium_stability.ruzic_fiflis_2016 import RuzicInputs, evaluate_dict

    k_a_m = delta_b_t / MU0
    j_a_m2 = k_a_m / REFERENCE_LITHIUM["lithium_layer_thickness_m"]
    result = evaluate_dict(RuzicInputs(
        current_density_ka_m2=j_a_m2 / 1000.0,
        magnetic_field_t=REFERENCE_LITHIUM["background_B_T"] + abs(delta_b_t),
        plasma_tangential_velocity_km_s=REFERENCE_LITHIUM["lithium_velocity_km_s"],
        trench_width_mm=REFERENCE_LITHIUM["trench_width_mm"],
        jb_angle_deg=angle_deg,
        wetted=REFERENCE_LITHIUM["wetted"],
    ))
    result.update({
        "classification": "IDEALIZED_MAGNETOSTATIC_TRANSFER_ONLY",
        "deltaB_control_T": delta_b_t,
        "K_required_A_per_m": k_a_m,
        "assumed_current_path_thickness_m": REFERENCE_LITHIUM["lithium_layer_thickness_m"],
        "J_Li_A_per_m2": j_a_m2,
        "current_direction": "idealized tangential sheet current",
        "local_total_B_T": REFERENCE_LITHIUM["background_B_T"] + abs(delta_b_t),
        "source": REFERENCE_LITHIUM["source"],
    })
    return result


def write_selection_and_lithium_bridge() -> None:
    transfer = json.loads((OUT / "magnetic_operator_transfer_summary.json").read_text())
    sustained_path = OUT / "magnetic_operator_sustained_summary.json"
    sustained = json.loads(sustained_path.read_text()) if sustained_path.exists() else {}
    selected = transfer.get("selected_transfer_sign") or "none"
    sustained_class = sustained.get("classification", "MAGNETIC_OPERATOR_PULSE_RESPONSE_ONLY")
    closed_loop_state = (
        "CLOSED_LOOP_HANDOFF_BLOCKED_BY_SUSTAINED_GATE"
        if sustained_class != "M3DC1_MAGNETIC_OPERATOR_SUSTAINED_SHEET_CONTROL"
        else "CLOSED_LOOP_HANDOFF_REQUIRES_LITHIUM_GATE"
    )
    (OUT / "magnetic_operator_selection.md").write_text(f"""# Magnetic Operator Selection

## Result

Selected plasma-side operator for this rung:

```text
localized flux/vector-potential source in flux_nolin
```

Short-pulse classification:

```text
{transfer["classification"]}
```

Sustained open-loop classification:

```text
{sustained_class}
```

The selected transfer sign is `{selected}`. In the short-pulse audit, `A=-0.01`
was the only sign with the immediate desired physical signature: sheet width
increased, peak `|Jphi|` decreased, and shoulder loading increased. The
zero-amplitude case was baseline-equivalent at the extracted times.

## Selection Boundary

This freezes one operator only for plasma-side evidence accounting. It does not
validate lithium current coupling, does not validate a boundary coil transfer
function, and does not justify closed-loop EARLY/AGGRESSIVE/HOLD control.

The sustained open-loop run over `0.0 <= t <= 0.25` did not maintain a wider
sheet. Its mean active width gain was
`{sustained.get("mean_active_width_gain_pct", float("nan")):.6g}%`, the minimum
active width gain was `{sustained.get("min_active_width_gain_pct", float("nan")):.6g}%`,
and the maximum active peak-current change was
`{sustained.get("max_active_Jpk_change_pct", float("nan")):.6g}%`.

Closed-loop handoff state:

```text
{closed_loop_state}
```

## Chain Kept Explicit

```text
commanded lithium current
  -> lithium/backing-conductor surface current K or J_Li
  -> local magnetic perturbation deltaB_control
  -> plasma magnetic boundary/edge perturbation
  -> current-sheet response
  -> topology/reconnection response
```

This rung only validates the middle plasma-side relation:

```text
deltaB_control proxy -> current-sheet response
```
""")

    (OUT / "lithium_to_field_mapping.md").write_text(f"""# Lithium-To-Field Mapping Boundary

Classification:

```text
LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED
```

The M3D-C1 magnetic operator is a normalized localized flux/vector-potential
source. The short-pulse result establishes field-level reachability inside the
GEM reconnecting ROI, but it does not provide a calibrated transfer from
`mag_ctrl_amp` to physical tesla at a liquid-lithium surface.

Therefore the lithium bridge is limited to:

```text
IDEALIZED_MAGNETOSTATIC_TRANSFER_ONLY
```

For an ideal tangential sheet-current geometry:

```text
deltaB_t ~= mu0 K
K = deltaB_t / mu0
J_Li = K / d_conductor
```

where `K` is surface current density in A/m and `d_conductor` is the assumed
current-carrying lithium/backing-conductor thickness. This relation is not the
machine transfer function and does not include coil geometry, wall geometry,
shielding, plasma response, conductor returns, or time-dependent circuit limits.

Reference reactor-design sensitivity values used only where a dimensional
sensitivity is explicitly labeled:

| Quantity | Value | Source |
|---|---:|---|
| Background field at lithium proxy | {REFERENCE_LITHIUM["background_B_T"]} T | {REFERENCE_LITHIUM["source"]} |
| Lithium velocity | {REFERENCE_LITHIUM["lithium_velocity_km_s"]} km/s | {REFERENCE_LITHIUM["source"]} |
| Current-path thickness proxy | {REFERENCE_LITHIUM["lithium_layer_thickness_m"]} m | {REFERENCE_LITHIUM["source"]} |
| Trench/wetted width for sensitivity | {REFERENCE_LITHIUM["trench_width_mm"]} mm | lower edge of repository Fig. 7A plotted-width range |
| Wetted assumption | {REFERENCE_LITHIUM["wetted"]} | required by repository Eq. 23 gate |

The Ruzic/Fiflis gate uses total local field:

```text
B_Li,total = B_background_at_Li + deltaB_control_at_Li
```

The current repository evidence does not supply `deltaB_control_at_Li` for the
M3D-C1 operator, so no lithium operating point is declared as viable.

Claim boundary preserved:

```text
FIFLIS/RUZIC 2016 REDUCED SURFACE-RETENTION GATE
```

It is not a complete free-surface MHD simulation, reactor survivability
validation, or proof of lithium-current -> plasma coupling. The J-B orientation
correction uses `|J| |sin(theta_JB)|`; that is a repository adaptation, not part
of Eq. 22 as printed.
""")

    sensitivity = []
    for delta_b in [0.001, 0.01, 0.05]:
        for angle in [90.0, 30.0, 10.0]:
            sensitivity.append(ruzic_row(delta_b, angle))
    write_csv(OUT / "lithium_field_mapping.csv", sensitivity)

    budget = []
    for state, note in [
        ("OFF", "no additional lithium control current"),
        ("BIAS", "standing shaping state not physically sized because transfer is unresolved"),
        ("EARLY", "pre-peak shaping state not physically sized because transfer is unresolved"),
        ("AGGRESSIVE_ON", "maximum demanded state not authorized; sustained plasma gate failed"),
        ("HOLD", "post-recovery nonzero state not authorized; sustained plasma gate failed"),
    ]:
        budget.append({
            "state": state,
            "mag_ctrl_amp_reference": 0.0 if state == "OFF" else "UNRESOLVED",
            "required_deltaB_T": 0.0 if state == "OFF" else "UNRESOLVED",
            "equivalent_K_A_per_m": 0.0 if state == "OFF" else "UNRESOLVED",
            "equivalent_J_Li_A_per_m2": 0.0 if state == "OFF" else "UNRESOLVED",
            "J_B_angle_deg": "UNRESOLVED",
            "total_local_B_T": REFERENCE_LITHIUM["background_B_T"] if state == "OFF" else "UNRESOLVED",
            "rt_term": 0.0 if state == "OFF" else "UNRESOLVED",
            "kh_term": 0.0 if state == "OFF" else "UNRESOLVED",
            "ruzic_x": 0.0 if state == "OFF" else "UNRESOLVED",
            "w_crit_mm": "inf" if state == "OFF" else "UNRESOLVED",
            "actual_trench_width_mm": REFERENCE_LITHIUM["trench_width_mm"],
            "width_margin_mm": "inf" if state == "OFF" else "UNRESOLVED",
            "stable_by_eq23": True if state == "OFF" else "NOT_EVALUATED_DIMENSIONAL_TRANSFER_UNRESOLVED",
            "domain_label": "IMPULSE_EXTRAPOLATION_FROM_FIG7A" if state == "OFF" else "DIMENSIONAL_LITHIUM_TRANSFER_UNRESOLVED",
            "wetting_label": "WETTED_ASSUMPTION",
            "note": note,
        })
    write_csv(OUT / "lithium_controller_state_budget.csv", budget)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(__import__("sys").argv) == 1 or __import__("sys").argv[1] == "summarize":
        summarize()
        write_inventory()
        write_selection_and_lithium_bridge()
    elif __import__("sys").argv[1] == "prepare":
        write_inventory()
        for name, amp in MATRIX:
            prepare_run(name, amp)
        prepare_custom_run(SUSTAINED[0], SUSTAINED[1], SUSTAINED[2], SUSTAINED[3], 5)
    elif __import__("sys").argv[1] == "run":
        for name, _ in MATRIX:
            run(["bash", "launch_command.sh"], cwd=RUN_ROOT / f"TCT_MAGOP_{name.upper()}", check=True)
        run(["bash", "launch_command.sh"], cwd=RUN_ROOT / f"TCT_MAGOP_{SUSTAINED[0].upper()}", check=True)
    else:
        raise SystemExit("usage: prepare | run | summarize")


if __name__ == "__main__":
    main()
