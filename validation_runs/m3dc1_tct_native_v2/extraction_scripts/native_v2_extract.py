#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, re, subprocess, sys
from pathlib import Path

H5DUMP = Path("/home/ubuntu/spack/opt/spack/linux-skylake/hdf5-1.14.6-uoyar6dpmk3uncnm7a5mogs4losjyziw/bin/h5dump")
COLS = ["ntime","time","ekin","gamma_gr","ekinp","ekint","ekin3","emagp","emagt","emag3","etot"]
SCALARS = ["time","Reconnected_Flux","psi0","psi_lcfs","psimin","xmag","zmag","xnull","znull","toroidal_current","toroidal_flux","volume","loop_voltage"]

def run(cmd):
    return subprocess.run([str(x) for x in cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout

def nums(s):
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?|[-+]?\.\d+(?:[Ee][-+]?\d+)?", s)]

def h5data(path: Path, dataset: str):
    text = run([H5DUMP, "-y", "-w", "0", "-d", dataset, path])
    m = re.search(r"DATA \{(.*?)\}\s*}\s*}", text, re.S)
    return nums(m.group(1)) if m else []

def h5shape(path: Path, dataset: str):
    text = run([H5DUMP, "-H", "-d", dataset, path])
    m = re.search(r"DATASPACE\s+SIMPLE\s+\{\s*\(\s*([0-9, ]+)\)", text)
    return tuple(int(x.strip()) for x in m.group(1).split(",")) if m else ()

def matrix(path: Path, dataset: str):
    shape = h5shape(path, dataset)
    data = h5data(path, dataset)
    if len(shape) != 2 or len(data) != shape[0] * shape[1]:
        raise RuntimeError(f"bad shape/data for {path}:{dataset}: {shape} {len(data)}")
    return [data[i*shape[1]:(i+1)*shape[1]] for i in range(shape[0])]

def scalar_series(run_dir: Path):
    c1 = run_dir / "C1.h5"
    out = {}
    for name in SCALARS:
        out[name] = h5data(c1, f"/scalars/{name}")
    return out

def c1ke(run_dir: Path):
    rows=[]
    with (run_dir/"C1ke").open() as f:
        for line in f:
            if line.strip(): rows.append(dict(zip(COLS, [float(x) for x in line.split()])))
    return rows

def run_status(run_dir: Path):
    p=run_dir/"run_status.txt"
    return p.read_text().strip() if p.exists() else "missing"

def text_has_bad(run_dir: Path):
    txt=(run_dir/"C1stdout").read_text(errors="replace") if (run_dir/"C1stdout").exists() else ""
    return bool(re.search(r"(?<![A-Za-z])(?:NaN|Inf)(?![A-Za-z])", txt, re.I)), re.findall(r"WARNING:.*|Warning:.*|ERROR:.*|Error:.*", txt)

def centers(run_dir: Path, tindex: int):
    elems = matrix(run_dir / f"time_{tindex:03d}.h5", "/mesh/elements")
    # M3D-C1 output writes eight element values. In this 2-D GEM output, columns 5 and 6
    # are the physical R,Z element-center coordinates used for field localization diagnostics.
    return [(row[4], row[5]) for row in elems]

def field_first(run_dir: Path, tindex: int, name: str):
    mat = matrix(run_dir / f"time_{tindex:03d}.h5", f"/fields/{name}")
    # First coefficient is used as the element-center/mean diagnostic value. Higher coefficients
    # are retained in max_abs_coeff for QA but not treated as pointwise physical extrema.
    return [row[0] for row in mat], max(abs(x) for row in mat for x in row)

def field_names(run_dir: Path, tindex: int):
    return run([H5DUMP, "-n", run_dir / f"time_{tindex:03d}.h5"])

def timestep_metrics(run_dir: Path, tindex: int, source_center=None):
    rz = centers(run_dir, tindex)
    j, j_coeff = field_first(run_dir, tindex, "jphi")
    psi, psi_coeff = field_first(run_dir, tindex, "psi")
    try:
        cd, cd_coeff = field_first(run_dir, tindex, "cd_source")
    except Exception:
        cd, cd_coeff = [0.0]*len(j), 0.0
    absj = [abs(x) for x in j]
    imax = max(range(len(absj)), key=absj.__getitem__)
    maxj = absj[imax]
    thresh = 0.5 * maxj if maxj > 0 else 0.0
    hi = [i for i,a in enumerate(absj) if a >= thresh]
    high_loading = sum(absj[i] for i in hi)
    total_loading = sum(absj)
    if hi:
        rvals = [rz[i][0] for i in hi]; zvals = [rz[i][1] for i in hi]
        fwhm_r = max(rvals)-min(rvals); fwhm_z = max(zvals)-min(zvals)
        cent_r = sum(rz[i][0]*absj[i] for i in hi)/sum(absj[i] for i in hi)
        cent_z = sum(rz[i][1]*absj[i] for i in hi)/sum(absj[i] for i in hi)
    else:
        fwhm_r=fwhm_z=cent_r=cent_z=math.nan
    src_amp = max(abs(x) for x in cd) if cd else 0.0
    src_i = max(range(len(cd)), key=lambda i: abs(cd[i])) if cd else 0
    src_r, src_z = rz[src_i] if cd else (math.nan, math.nan)
    if source_center:
        src_r, src_z = source_center
    return {
        "max_abs_jphi": maxj,
        "max_abs_jphi_all_coeffs_QA": j_coeff,
        "max_jphi_R": rz[imax][0],
        "max_jphi_Z": rz[imax][1],
        "integrated_abs_jphi": total_loading,
        "integrated_high_jphi_halfmax": high_loading,
        "sheet_centroid_R": cent_r,
        "sheet_centroid_Z": cent_z,
        "sheet_fwhm_R": fwhm_r,
        "sheet_fwhm_Z": fwhm_z,
        "psi_min_field_center": min(psi),
        "psi_max_field_center": max(psi),
        "cd_source_peak_center_coeff": src_amp,
        "cd_source_peak_all_coeffs_QA": cd_coeff,
        "cd_source_R": src_r,
        "cd_source_Z": src_z,
        "distance_source_to_maxJ": math.hypot(src_r-rz[imax][0], src_z-rz[imax][1]) if math.isfinite(src_r) else math.nan,
        "distance_source_to_sheet_centroid": math.hypot(src_r-cent_r, src_z-cent_z) if math.isfinite(src_r) and math.isfinite(cent_r) else math.nan,
    }

def timeseries(run_dir: Path, source_center=None):
    scal = scalar_series(run_dir); ke = c1ke(run_dir); rows=[]
    for i,k in enumerate(ke):
        m = timestep_metrics(run_dir, i, source_center=source_center)
        row={"ntime": int(k["ntime"]), "time": k["time"], "kinetic_energy": k["ekin"], "magnetic_energy": k["emagp"]+k["emagt"]+k["emag3"], "total_energy": k["etot"]}
        for s,v in scal.items(): row[s] = v[i] if i < len(v) else math.nan
        row.update(m); rows.append(row)
    # finite-difference reconnection rate
    for a,b in zip(rows, rows[1:]):
        dt=b["time"]-a["time"]
        b["d_reconnected_flux_dt"]=(b["Reconnected_Flux"]-a["Reconnected_Flux"])/dt if dt else math.nan
    if rows: rows[0]["d_reconnected_flux_dt"] = math.nan
    return rows

def write_csv(path: Path, rows):
    if not rows: return
    with path.open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def rel(new, old):
    return None if abs(old) < 1e-30 else (new-old)/old

def gate(run_dir: Path, reference: Path|None=None, field_reference: Path|None=None):
    bad,warns=text_has_bad(run_dir); rows=timeseries(run_dir)
    t0=rows[0]
    checks={k: math.isfinite(float(t0[k])) for k in ["volume","magnetic_energy","kinetic_energy","toroidal_current","toroidal_flux","Reconnected_Flux","max_abs_jphi"]}
    ref={"available": False}
    if reference:
        ref_rows=timeseries(reference)
        keys=["volume","magnetic_energy","kinetic_energy","toroidal_current","toroidal_flux","Reconnected_Flux","max_abs_jphi","integrated_abs_jphi"]
        ref={"available": True, "run_dir": str(reference), "t0_abs_diff": {k: abs(t0[k]-ref_rows[0][k]) for k in keys}}
    field_ref={"available": False}
    if field_reference:
        diffs={}
        for ds in ["psi","jphi","I","phi","V","E_R","E_PHI","E_Z","E_par"]:
            a=field_first(run_dir,0,ds)[0]; b=field_first(field_reference,0,ds)[0]
            diffs[ds]=max(abs(x-y) for x,y in zip(a,b))
        field_ref={"available": True, "max_abs_field_diff_t0": diffs}
    ok = run_status(run_dir)=="return_code=0" and t0["volume"]>0 and all(checks.values()) and not bad
    if field_reference and any(v > 1e-12 for v in field_ref["max_abs_field_diff_t0"].values()): ok=False
    return {"status": "PASS" if ok else "FAIL", "run_dir": str(run_dir), "run_status": run_status(run_dir), "finite_checks": checks, "volume": t0["volume"], "magnetic_energy": t0["magnetic_energy"], "kinetic_energy": t0["kinetic_energy"], "toroidal_current": t0["toroidal_current"], "Reconnected_Flux": t0["Reconnected_Flux"], "max_abs_jphi": t0["max_abs_jphi"], "reference_check": ref, "field_reference_check": field_ref, "warnings": warns, "fail_reason": None if ok else "runtime/nonfinite/zero-volume/t0-field-equivalence failure"}

def summarize_pair(base, ctrl):
    b=timeseries(base); c=timeseries(ctrl)
    peak_b=max(r["max_abs_jphi"] for r in b); peak_c=max(r["max_abs_jphi"] for r in c)
    int_b=sum(r["integrated_high_jphi_halfmax"] for r in b); int_c=sum(r["integrated_high_jphi_halfmax"] for r in c)
    rf_peak_b=max(abs(r["Reconnected_Flux"]) for r in b); rf_peak_c=max(abs(r["Reconnected_Flux"]) for r in c)
    rate_b=max(abs(r["d_reconnected_flux_dt"]) for r in b if math.isfinite(r["d_reconnected_flux_dt"])); rate_c=max(abs(r["d_reconnected_flux_dt"]) for r in c if math.isfinite(r["d_reconnected_flux_dt"]));
    return {
      "peak_abs_jphi_baseline": peak_b, "peak_abs_jphi_controlled": peak_c, "peak_abs_jphi_change_fraction": rel(peak_c, peak_b),
      "integrated_high_jphi_baseline": int_b, "integrated_high_jphi_controlled": int_c, "integrated_high_jphi_change_fraction": rel(int_c, int_b),
      "final_reconnected_flux_baseline": b[-1]["Reconnected_Flux"], "final_reconnected_flux_controlled": c[-1]["Reconnected_Flux"], "final_reconnected_flux_change_fraction": rel(c[-1]["Reconnected_Flux"], b[-1]["Reconnected_Flux"]),
      "peak_abs_reconnected_flux_change_fraction": rel(rf_peak_c, rf_peak_b), "peak_reconnection_rate_change_fraction": rel(rate_c, rate_b),
      "final_magnetic_energy_change_fraction": rel(c[-1]["magnetic_energy"], b[-1]["magnetic_energy"]), "final_kinetic_energy_change_fraction": rel(c[-1]["kinetic_energy"], b[-1]["kinetic_energy"]),
      "baseline_peak_time": max(b, key=lambda r:r["max_abs_jphi"])["time"], "controlled_peak_time": max(c, key=lambda r:r["max_abs_jphi"])["time"]
    }

def main():
    if len(sys.argv) < 4:
        raise SystemExit("usage: native_v2_extract.py OUT BASE CTRL [ZERO] [FALS]")
    out=Path(sys.argv[1]); base=Path(sys.argv[2]); ctrl=Path(sys.argv[3]); zero=Path(sys.argv[4]) if len(sys.argv)>4 and sys.argv[4] != "-" else None; fals=Path(sys.argv[5]) if len(sys.argv)>5 and sys.argv[5] != "-" else None
    out.mkdir(parents=True, exist_ok=True)
    b=timeseries(base); c=timeseries(ctrl)
    write_csv(out/"native_v2_baseline_field_timeseries.csv", b)
    write_csv(out/"native_v2_controlled_field_timeseries.csv", c)
    pair=[]
    for rb,rc in zip(b,c):
        row={"time": rb["time"], "baseline_max_abs_jphi": rb["max_abs_jphi"], "controlled_max_abs_jphi": rc["max_abs_jphi"], "max_abs_jphi_change_fraction": rel(rc["max_abs_jphi"], rb["max_abs_jphi"]), "baseline_integrated_high_jphi": rb["integrated_high_jphi_halfmax"], "controlled_integrated_high_jphi": rc["integrated_high_jphi_halfmax"], "integrated_high_jphi_change_fraction": rel(rc["integrated_high_jphi_halfmax"], rb["integrated_high_jphi_halfmax"]), "baseline_sheet_fwhm_R": rb["sheet_fwhm_R"], "controlled_sheet_fwhm_R": rc["sheet_fwhm_R"], "baseline_sheet_fwhm_Z": rb["sheet_fwhm_Z"], "controlled_sheet_fwhm_Z": rc["sheet_fwhm_Z"], "baseline_Reconnected_Flux": rb["Reconnected_Flux"], "controlled_Reconnected_Flux": rc["Reconnected_Flux"], "Reconnected_Flux_change_fraction": rel(rc["Reconnected_Flux"], rb["Reconnected_Flux"]), "baseline_dReconnected_Flux_dt": rb["d_reconnected_flux_dt"], "controlled_dReconnected_Flux_dt": rc["d_reconnected_flux_dt"], "baseline_magnetic_energy": rb["magnetic_energy"], "controlled_magnetic_energy": rc["magnetic_energy"], "magnetic_energy_change_fraction": rel(rc["magnetic_energy"], rb["magnetic_energy"]), "baseline_kinetic_energy": rb["kinetic_energy"], "controlled_kinetic_energy": rc["kinetic_energy"], "kinetic_energy_change_fraction": rel(rc["kinetic_energy"], rb["kinetic_energy"])}
        pair.append(row)
    write_csv(out/"native_v2_pair_timeseries.csv", pair)
    geom=[{"time": r["time"], "actuator_R": c[i]["cd_source_R"], "actuator_Z": c[i]["cd_source_Z"], "source_peak": c[i]["cd_source_peak_center_coeff"], "maxJ_R": c[i]["max_jphi_R"], "maxJ_Z": c[i]["max_jphi_Z"], "sheet_centroid_R": c[i]["sheet_centroid_R"], "sheet_centroid_Z": c[i]["sheet_centroid_Z"], "xpoint_R": c[i]["xnull"], "xpoint_Z": c[i]["znull"], "opoint_R": c[i]["xmag"], "opoint_Z": c[i]["zmag"], "distance_source_to_maxJ": c[i]["distance_source_to_maxJ"], "distance_source_to_sheet_centroid": c[i]["distance_source_to_sheet_centroid"], "distance_source_to_xpoint": math.hypot(c[i]["cd_source_R"]-c[i]["xnull"], c[i]["cd_source_Z"]-c[i]["znull"]) if math.isfinite(c[i]["xnull"]) else math.nan} for i,r in enumerate(c)]
    write_csv(out/"actuator_coupling_geometry.csv", geom)
    summary=summarize_pair(base, ctrl)
    measurable=abs(summary["peak_abs_jphi_change_fraction"] or 0)>1e-4 or abs(summary["integrated_high_jphi_change_fraction"] or 0)>1e-4
    current_reduced=(summary["peak_abs_jphi_change_fraction"] or 0)<0 and (summary["integrated_high_jphi_change_fraction"] or 0)<0
    topo_worse=(summary["peak_reconnection_rate_change_fraction"] or 0)>0.05 or (summary["peak_abs_reconnected_flux_change_fraction"] or 0)>0.05
    coupling=min((g["distance_source_to_sheet_centroid"] for g in geom[1:] if math.isfinite(g["distance_source_to_sheet_centroid"])), default=math.inf)
    if not measurable: cls="NATIVE_TCT_V2_NO_MEASURABLE_EFFECT"
    elif coupling > 0.5: cls="NATIVE_TCT_V2_ACTUATOR_COUPLING_FAILURE"
    elif current_reduced and topo_worse: cls="NATIVE_TCT_V2_CURRENT_REDUCTION_TOPOLOGY_WORSE"
    elif current_reduced and not topo_worse: cls="NATIVE_TCT_V2_LOCAL_CURRENT_AND_TOPOLOGY_IMPROVEMENT"
    else: cls="NATIVE_TCT_V2_GENERIC_SOURCE_EFFECT"
    summary.update({"classification": cls, "baseline_run": str(base), "controlled_run": str(ctrl), "minimum_source_to_sheet_centroid_distance": coupling})
    (out/"native_v2_pair_summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    with (out/"native_v2_pair_metrics.csv").open("w", newline="") as f:
        w=csv.writer(f); w.writerow(["metric","value","definition"])
        for k,v in summary.items(): w.writerow([k,v,"field-level element-center jphi and native scalar diagnostics"])
    (out/"initialization_gate_baseline.json").write_text(json.dumps(gate(base), indent=2)+"\n")
    if zero: (out/"zero_amplitude_equivalence.json").write_text(json.dumps(gate(zero, reference=base, field_reference=base), indent=2)+"\n")
    (out/"initialization_gate_controlled.json").write_text(json.dumps(gate(ctrl, reference=base, field_reference=base), indent=2)+"\n")
    if fals:
        fs=summarize_pair(base, fals); fs["classification_note"]="displaced source falsification; compare response locality against controlled"
        (out/"falsification_summary.json").write_text(json.dumps(fs, indent=2)+"\n")

if __name__ == "__main__": main()
