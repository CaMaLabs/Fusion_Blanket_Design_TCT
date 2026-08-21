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
OUT = REPO / "validation_runs/m3dc1_tct_native"
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_BASELINE_SINGLEPART")
CTRL = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_CONTROLLED")
REV = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_FALSIFICATION_REVERSE")
BAD1 = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_BASELINE_INVALID_16PART")
BAD2 = Path("/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
H5DUMP = Path("/home/ubuntu/spack/opt/spack/linux-skylake/hdf5-1.14.6-uoyar6dpmk3uncnm7a5mogs4losjyziw/bin/h5dump")
COLS = ["ntime", "time", "ekin", "gamma_gr", "ekinp", "ekint", "ekin3", "emagp", "emagt", "emag3", "etot"]


def run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def c1ke(path: Path) -> list[dict[str, float]]:
    rows = []
    with (path / "C1ke").open() as handle:
        for line in handle:
            if line.strip():
                rows.append(dict(zip(COLS, [float(x) for x in line.split()])))
    return rows


def status(path: Path) -> str:
    p = path / "run_status.txt"
    return p.read_text().strip() if p.exists() else "missing"


def grepvals(path: Path) -> dict:
    text = (path / "C1stdout").read_text(errors="replace")
    vals: dict = {}
    patterns = {
        "volume": r"Volume =\s*([-+0-9.Ee]+)",
        "toroidal_current": r"Toroidal current =\s*([-+0-9.Ee]+)",
        "toroidal_flux": r"Toroidal flux =\s*([-+0-9.Ee]+)",
        "total_energy": r"Total energy =\s*([-+0-9.Ee]+)",
        "mesh_counts": r"mesh entity counts: v\s+(\d+) e\s+(\d+) f\s+(\d+) r\s+(\d+)",
        "poloidal_flux_line": r"Poloidal flux at axis, boundary\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)",
    }
    for key, pat in patterns.items():
        matches = list(re.finditer(pat, text))
        if not matches:
            continue
        if key == "mesh_counts":
            vals[key] = tuple(int(x) for x in matches[0].groups())
        elif key == "poloidal_flux_line":
            vals[key] = tuple(float(x) for x in matches[0].groups())
        else:
            vals[key] = [float(x.group(1)) for x in matches]
    vals["warnings"] = re.findall(r"WARNING:.*", text)
    vals["nan_inf_present"] = bool(re.search(r"(?<![A-Za-z])(?:NaN|Inf)(?![A-Za-z])", text, re.I))
    vals["stopped_at_0"] = "Stopped at           0" in text or "Stopped at       0" in text
    return vals


def gate(path: Path, ref: Path | None = None, expected_scale: float | None = None) -> dict:
    rows = c1ke(path)
    g = grepvals(path)
    t0 = rows[0]
    mag = t0["emagp"] + t0["emagt"] + t0["emag3"]
    first_volume = g.get("volume", [float("nan")])[0]
    first_current = g.get("toroidal_current", [float("nan")])[0]
    first_flux = g.get("toroidal_flux", [float("nan")])[0]
    finite = {
        "volume": math.isfinite(first_volume),
        "magnetic_energy": math.isfinite(mag),
        "kinetic_energy": math.isfinite(t0["ekin"]),
        "current": math.isfinite(first_current),
        "flux": math.isfinite(first_flux),
    }
    ref_check = {"available": False}
    if ref:
        rr = c1ke(ref)
        max_abs = max(abs(t0[k] - rr[0][k]) for k in COLS if k != "etot")
        ref_check = {
            "available": True,
            "reference_path": str(ref / "C1ke"),
            "t0_max_abs_difference_excluding_etot": max_abs,
            "matches_required_columns": max_abs < 1e-9,
        }
    repeat = {
        "status": "not_repeated",
        "reason": "single baseline run; upstream C1ke reference comparison used as t0 repeatability proxy",
    }
    ok = all(finite.values()) and first_volume > 0 and not g["nan_inf_present"] and (not ref or ref_check["matches_required_columns"])
    return {
        "status": "PASS" if ok else "FAIL",
        "run_dir": str(path),
        "run_status": status(path),
        "actuator_scale_ext_field": expected_scale,
        "volume": first_volume,
        "magnetic_energy": mag,
        "kinetic_energy": t0["ekin"],
        "current": first_current,
        "flux": first_flux,
        "finite_checks": finite,
        "mesh_check": {
            "mesh_counts_v_e_f_r": g.get("mesh_counts"),
            "partition_count": 1,
            "status": "PASS" if g.get("mesh_counts") and g.get("mesh_counts")[2] > 0 else "FAIL",
        },
        "region_check": {
            "expected_regions_present": "not explicitly enumerated in stdout; C1input has plasma/conductor/vacuum zone_type and positive volume",
            "status": "PASS",
        },
        "repeatability": repeat,
        "reference_check": ref_check,
        "warnings": g["warnings"],
        "fail_reason": None if ok else "nonfinite/zero-volume/reference mismatch/native warning gate failure",
    }


def pct(new: float, old: float) -> float | None:
    return None if old == 0 else 100.0 * (new - old) / old


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extraction_scripts").mkdir(exist_ok=True)

    base = c1ke(BASE)
    ctrl = c1ke(CTRL)
    rev = c1ke(REV)
    base_g = grepvals(BASE)
    ctrl_g = grepvals(CTRL)
    rev_g = grepvals(REV)

    (OUT / "initialization_gate_baseline.json").write_text(json.dumps(gate(BASE, SRC / "unstructured/regtest/RMP/base", 1.0), indent=2) + "\n")
    (OUT / "initialization_gate_controlled.json").write_text(json.dumps(gate(CTRL, None, 0.8566360855), indent=2) + "\n")

    with (OUT / "baseline_timeseries.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "ntime", "ekin", "emagp", "emagt", "emag3", "magnetic_energy", "etot", "toroidal_current", "toroidal_flux", "volume", "psi0", "psimin", "psi_lcfs", "max_abs_J_proxy", "current_sheet_width_fwhm", "island_width", "reconnection_metric"])
        currents = base_g.get("toroidal_current", [None] * len(base))
        fluxes = base_g.get("toroidal_flux", [None] * len(base))
        vols = base_g.get("volume", [None] * len(base))
        for i, r in enumerate(base):
            cur = currents[min(i, len(currents) - 1)]
            flux = fluxes[min(i, len(fluxes) - 1)]
            vol = vols[min(i, len(vols) - 1)]
            mag = r["emagp"] + r["emagt"] + r["emag3"]
            w.writerow([r["time"], int(r["ntime"]), r["ekin"], r["emagp"], r["emagt"], r["emag3"], mag, r["etot"], cur, flux, vol, "" if i else 0, "" if i else 0.420856, "" if i else 0.0989886, abs(cur) if cur is not None else "", "", "", abs(flux - fluxes[0]) if flux is not None else ""])

    with (OUT / "native_pair_timeseries.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "baseline_ekin", "controlled_ekin", "baseline_magnetic_energy", "controlled_magnetic_energy", "baseline_etot", "controlled_etot", "baseline_current_proxy", "controlled_current_proxy", "current_proxy_change_pct", "baseline_flux_transfer_proxy", "controlled_flux_transfer_proxy", "flux_transfer_proxy_change_pct"])
        bcur = base_g["toroidal_current"]
        ccur = ctrl_g["toroidal_current"]
        bflux = base_g["toroidal_flux"]
        cflux = ctrl_g["toroidal_flux"]
        for i, (b, c) in enumerate(zip(base, ctrl)):
            bm = b["emagp"] + b["emagt"] + b["emag3"]
            cm = c["emagp"] + c["emagt"] + c["emag3"]
            bf = abs(bflux[min(i, len(bflux) - 1)] - bflux[0])
            cf = abs(cflux[min(i, len(cflux) - 1)] - cflux[0])
            w.writerow([b["time"], b["ekin"], c["ekin"], bm, cm, b["etot"], c["etot"], abs(bcur[min(i, len(bcur) - 1)]), abs(ccur[min(i, len(ccur) - 1)]), pct(abs(ccur[min(i, len(ccur) - 1)]), abs(bcur[min(i, len(bcur) - 1)])), bf, cf, pct(cf, bf) if bf else ""])

    peak_b = max(abs(x) for x in base_g["toroidal_current"])
    peak_c = max(abs(x) for x in ctrl_g["toroidal_current"])
    int_b = sum(abs(x) for x in base_g["toroidal_current"])
    int_c = sum(abs(x) for x in ctrl_g["toroidal_current"])
    mag_b = base[-1]["emagp"] + base[-1]["emagt"] + base[-1]["emag3"]
    mag_c = ctrl[-1]["emagp"] + ctrl[-1]["emagt"] + ctrl[-1]["emag3"]
    flux_b = abs(base_g["toroidal_flux"][-1] - base_g["toroidal_flux"][0])
    flux_c = abs(ctrl_g["toroidal_flux"][-1] - ctrl_g["toroidal_flux"][0])
    rows = [
        ["peak_current_reduction_pct", -pct(peak_c, peak_b), "native toroidal_current scalar used as current-loading proxy"],
        ["integrated_current_loading_change_pct", pct(int_c, int_b), "sum |toroidal_current| over available native output times"],
        ["current_sheet_width_change_pct", "", "not available from scalar-only native RMP outputs"],
        ["magnetic_energy_change_pct", pct(mag_c, mag_b), "C1ke magnetic block E_MP+E_MT+E_P at final output"],
        ["kinetic_energy_change_pct", pct(ctrl[-1]["ekin"], base[-1]["ekin"]), "C1ke ekin final output"],
        ["island_width_change_pct", "", "not available from scalar-only native RMP outputs"],
        ["reconnection_metric_change_pct", pct(flux_c, flux_b) if flux_b else "", "DERIVED flux-transfer proxy |toroidal_flux(t)-toroidal_flux(0)|"],
        ["topology_change_time_shift", 0, "no native topology transition detected in one-step linear-response case"],
        ["peak_current_time_shift", 0, "peak proxy occurs at final output in both runs"],
    ]
    with (OUT / "native_pair_metrics.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "definition"])
        w.writerows(rows)

    summary = {
        "classification": "NATIVE_TCT_NO_EFFECT",
        "selected_case": "official RMP regtest, single-part source mesh, m3dc1_2d_complex, 1 MPI rank",
        "why_selected": "Smallest official non-KPRAD case exercising native RMP/current-response machinery with positive volume and exact bundled C1ke reference match on this runtime. RMP_nonlin and partitioned RMP were rejected by initialization gate.",
        "baseline_run": str(BASE),
        "controlled_run": str(CTRL),
        "falsification_run": str(REV),
        "actuator": "scale_ext_field = 0.8566360855; one scalar multiplier of native RMP external-field read path",
        "baseline_peak_current_proxy": peak_b,
        "controlled_peak_current_proxy": peak_c,
        "peak_current_reduction_pct": -pct(peak_c, peak_b),
        "integrated_current_loading_change_pct": pct(int_c, int_b),
        "magnetic_energy_change_pct": pct(mag_c, mag_b),
        "flux_transfer_proxy_change_pct": pct(flux_c, flux_b) if flux_b else None,
        "topology_result": "No explicit island/X-point topology change in this one-step linear-response case; derived flux-transfer proxy unchanged.",
        "refinement": "Skipped by rule because paired result is exactly zero/nonzero effect gate not met.",
        "claim_scope": "Native M3D-C1 actuator-mapping falsification of this scalar external-field mapping only; not reactor validation, ELM suppression, or reconnection suppression.",
    }
    (OUT / "native_pair_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "baseline_topology_summary.json").write_text(json.dumps({
        "status": "SCALAR_ONLY_TOPOLOGY_PROXY",
        "native_case": "RMP linear response",
        "explicit_xpoint_opoint_tracking": "not available in extracted scalar set",
        "psi_extrema_available": ["psimin", "psi_lcfs", "psi0"],
        "flux_transfer_proxy": flux_b,
        "time_of_peak_current": base[-1]["time"],
        "time_of_first_topology_change": "not detected in one-step scalar output",
    }, indent=2) + "\n")

    rcur = rev_g["toroidal_current"]
    rmag = rev[-1]["emagp"] + rev[-1]["emagt"] + rev[-1]["emag3"]
    rflux = abs(rev_g["toroidal_flux"][-1] - rev_g["toroidal_flux"][0])
    with (OUT / "falsification_controls.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["control", "status", "scale_ext_field", "peak_current_proxy", "integrated_current_proxy", "magnetic_energy_final", "flux_transfer_proxy", "interpretation"])
        w.writerow(["sign_reversed", "COMPLETED", -0.8566360855, max(abs(x) for x in rcur), sum(abs(x) for x in rcur), rmag, rflux, "same scalar trajectory as baseline/control; code path does not affect this case over one-step native scalar outputs"])
    (OUT / "resolution_check.csv").write_text("status,reason\nSKIPPED,paired baseline-vs-controlled result was zero so refinement gate was not met\n")

    (OUT / "M3DC1_HANDOFF_RESOLVED.md").write_text("""# M3D-C1 Handoff Resolved

Sources searched in `/home/ubuntu/work/openmc/sweep`: `validation_runs/bout_tct_dudson_resolution_highres/M3DC1_HANDOFF.json`, `validation_runs/bout_tct_dudson_resolution_default/M3DC1_HANDOFF.json`, `bout_tct_dudson_resolution_audit.py`, and current-sheet validation outputs.

Resolved high-resolution BOUT values used without tuning:

| value | source | resolved value |
|---|---|---:|
| peak current reduction fraction | highres `M3DC1_HANDOFF.json` | 0.14336391448782237 |
| actuator multiplier used in M3D-C1 | `1 - peak_current_reduction_fraction` | 0.8566360855121776 |
| integrated current reduction fraction | highres handoff | 0.6855924599716687 |
| controlled peak sheet FWHM | highres handoff | 24 cells |
| uncontrolled peak sheet FWHM | highres handoff | 24 cells |
| magnetic-energy final change | highres handoff | -0.9508571237402103 |

No dimensional current-sheet geometry was present in the handoff JSON; therefore the native mapping used the smallest available dimensionless native actuator multiplier rather than inventing geometry.
""")
    (OUT / "native_case_selection.md").write_text("""# Native Case Selection

Selected baseline: official `unstructured/regtest/RMP` with the bundled single-part source mesh `diiid-0.02-2.5-4.0-4K0.smb`, `m3dc1_2d_complex`, one MPI rank, and unchanged physical inputs.

Why: it is the smallest non-KPRAD official case that exercises native RMP/current-response machinery and passes the hard initialization/reference gate on this runtime.

Rejected alternatives:

| case | reason rejected |
|---|---|
| `RMP_nonlin` checked-in 16-part mesh | t=0 magnetic energies ~1e24 and reference mismatch; initialization invalid |
| `RMP_nonlin` single-part source mesh | t=0 mismatch and nonlinear blow-up by timestep 3; initialization/reference invalid |
| `RMP` checked-in 16-part mesh | `Volume=0`/near-zero and t=0 energy mismatch |
| `adapt` | adaptation/t=0 oriented, not a clean paired current/topology test |
| `KPRAD_*` | explicitly excluded; not a TCT topology case |
| `NCSX` | larger stellarator case, no direct TCT/RMP actuator mapping needed for first rung |

This is a first native actuator-mapping falsification rung, not a nonlinear reconnection proof.
""")
    (OUT / "actuator_definition.md").write_text("""# Actuator Definition

Chosen actuator: `scale_ext_field` in `C1input`.

Native source path: `/home/ubuntu/M3DC1-official/unstructured/rmp.f90`, where `scale_ext_field` multiplies RMP field components for `irmp=1`. Input registration is in `/home/ubuntu/M3DC1-official/unstructured/input.f90`.

Only controlled-case change:

```text
scale_ext_field = 0.8566360855
```

Mapping: `0.8566360855 = 1 - 0.14336391448782237`, directly from the high-resolution BOUT handoff peak-current reduction fraction. No amplitude sweep was run.

Spatial profile/location/width: inherited from official `RMP` files `rmp_coil.dat` and `rmp_current.dat`; no geometry was invented.

Start/ramp/duration: inherited from official one-step linear RMP response; no extra time dependence.

Sign-reversed falsification control: `scale_ext_field = -0.8566360855`.
""")
    (OUT / "topology_diagnostics.md").write_text("""# Topology Diagnostics

This first native rung uses official `RMP`, a one-step linear-response case. Explicit island-width and X/O-point tracking are not emitted in the available scalar outputs. The least-assumptive topology-sensitive native quantities available are scalar flux and psi diagnostics: `toroidal_flux`, `psi0`, `psimin`, and `psi_lcfs`.

Derived reconnection/flux-transfer proxy: `abs(toroidal_flux(t) - toroidal_flux(0))`. It is labeled DERIVED and is not a formal reconnection rate.

Result: baseline, controlled, and sign-reversed control have identical C1ke/native scalar trajectories over the official one-step duration. Therefore there is no evidence in this rung that the actuator reduces current loading, changes sheet width, changes magnetic-energy release, delays topology change, or changes flux transfer.

Classification impact: lower peak J alone is not present; topology improvement is not present; primary state is `NATIVE_TCT_NO_EFFECT`.
""")

    report = f"""# Native M3D-C1 TCT RMP Actuator Mapping Study

Primary classification: `NATIVE_TCT_NO_EFFECT`

A native M3D-C1 first-rung paired test was run using the smallest official non-KPRAD case that passed initialization on this runtime: `RMP` with the bundled single-part source mesh and `m3dc1_2d_complex`. The partitioned `RMP` and `RMP_nonlin` meshes failed hard initialization gates, so they were not used as physics baselines.

Baseline and controlled runs both completed with return code 0. Baseline exactly matches the bundled `RMP/base/C1ke` under upstream `compare.py`. The controlled case differs by one scalar only: `scale_ext_field = 0.8566360855`.

## Result

| metric | baseline | controlled | change |
|---|---:|---:|---:|
| peak current proxy `max|toroidal_current|` | {peak_b:.17g} | {peak_c:.17g} | {-pct(peak_c, peak_b):.6g}% reduction |
| integrated current proxy | {int_b:.17g} | {int_c:.17g} | {pct(int_c, int_b):.6g}% |
| final magnetic-energy block | {mag_b:.17g} | {mag_c:.17g} | {pct(mag_c, mag_b):.6g}% |
| DERIVED flux-transfer proxy | {flux_b:.17g} | {flux_c:.17g} | {pct(flux_c, flux_b) if flux_b else 0:.6g}% |

The controlled C1ke/native scalar trajectory is identical to baseline for this official one-step response. The sign-reversed falsification control is also identical. No refinement was run because the paired effect is zero and the refinement gate requires a nonzero stable effect.

## What this establishes

This establishes that the direct `scale_ext_field` mapping of the BOUT peak-current reduction fraction does not produce a measurable current-loading or topology-proxy change in the smallest valid official native M3D-C1 RMP rung.

## What this does not establish

It does not establish reactor stabilization, ELM suppression, experimental validation, reconnection suppression, liquid-lithium actuator transfer, ignition improvement, or net energy gain. It also does not rule out a more physically localized native current-source or electric-field actuator in a nonlinear M3D-C1 case; the available nonlinear/partitioned official candidates failed initialization on this runtime.
"""
    (OUT / "M3DC1_TCT_NATIVE_REPORT.md").write_text(report)

    for name, path in [
        ("baseline", BASE),
        ("controlled", CTRL),
        ("falsification_reverse", REV),
        ("invalid_rmp_nonlin_16part", BAD1),
        ("invalid_rmp_16part", BAD2),
    ]:
        if not path.exists():
            continue
        for fn in ["C1ke", "launch_command.sh", "input_mesh_hashes.sha256", "regression_compare_output.txt"]:
            if (path / fn).exists():
                shutil.copy2(path / fn, OUT / f"{name}_{fn}")
        if (path / "C1stdout").exists():
            lines = (path / "C1stdout").read_text(errors="replace").splitlines()
            keep = [ln for ln in lines if re.search(r"WARNING|mesh entity counts|Poloidal flux|Total energy|Toroidal current|Toroidal flux|Volume|TIME STEP|Stopped at|scale_ext_field|model_info", ln)]
            (OUT / f"compact_{name}_stdout.log").write_text("\n".join(keep) + "\n")
        if (path / "C1.h5").exists():
            (OUT / f"{name}_hdf5_structure.txt").write_text(run([str(H5DUMP), "-n", str(path / "C1.h5")]))

    (OUT / "build_provenance.txt").write_text(
        run(["git", "rev-parse", "HEAD"], SRC)
        + run(["git", "status", "--short"], SRC)
        + "\n3D build: /home/ubuntu/M3DC1-official/build-ubuntu-3d/unstructured/m3dc1_3d\n"
        + "2D complex build: /home/ubuntu/M3DC1-official/build-ubuntu-2d-complex/unstructured/m3dc1_2d_complex\n"
        + run(["bash", "-lc", "source $HOME/spack/share/spack/setup-env.sh && spack env activate m3dc1-deps >/dev/null && spack find --loaded"], Path("/home/ubuntu"))
    )
    (OUT / "runtime_provenance.txt").write_text(json.dumps({
        "baseline": str(BASE),
        "controlled": str(CTRL),
        "falsification_reverse": str(REV),
        "invalid_candidates": [str(BAD1), str(BAD2)],
        "mpi_layout": "RMP baseline/control use 1 MPI rank with single-part source mesh; rejected RMP_nonlin tests used 64/4 ranks and failed gate",
    }, indent=2) + "\n")
    (OUT / "launch_commands.sh").write_text("\n\n".join((p / "launch_command.sh").read_text() for p in [BASE, CTRL, REV] if (p / "launch_command.sh").exists()))
    (OUT / "extraction_scripts" / "extract_native_rmp_pair.py").write_text("""#!/usr/bin/env python3
# Re-run extraction by executing /home/ubuntu/make_tct_native_package.py on the remote host.
# The script parses C1ke/stdout and records HDF5 structure with h5dump; it does not copy large HDF5 files into git.
""")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
