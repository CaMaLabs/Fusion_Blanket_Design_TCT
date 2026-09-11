#!/usr/bin/env python3
"""Uninterrupted native two-profile handoff refinement audit.

Profile 1 uses the best joint static shoulder frontier found so far.
At the handoff, profile 2 keeps the same center width and amplitude but changes
the shoulder width/separation, allowing a genuine spatial-profile handoff
without restart boundaries.

Two invariants must pass before physics is interpreted:
  * source=4 with zero amplitudes equals source=0 to 1e-12;
  * a same-profile handoff equals an uninterrupted constant-profile run to 1e-12.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import native_two_window_sustained_refinement_audit as native
import native_two_window_sustained_refinement_repair as repair
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_two_profile_handoff"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_two_profile_handoff_runs")

START = 0.05
HORIZON = 0.30
AMP = -0.015
PROFILE_WIDTH = 0.145
FIRST_SHOULDER_WIDTH = 0.34
FIRST_DELTA = 0.45

HANDOFF_TIMES = (0.12, 0.13)
SECOND_SHOULDER_WIDTHS = (0.34, 0.40)
SECOND_DELTAS = (0.30, 0.40)

EQ_TOL = 1e-12
MARKER = "! TCT two-profile second-window spatial profile"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def remove(path: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _ensure_module_vars() -> bool:
    modules = native.SRC / "unstructured/M3Dmodules.f90"
    text = modules.read_text()
    before = text
    declarations = (
        ("w_cd2", "  real :: W_cd2          ! second-window center-profile width"),
        ("w_cd2_shoulder", "  real :: W_cd2_shoulder ! second-window shoulder width"),
        ("delta_cd2", "  real :: delta_cd2      ! second-window shoulder separation"),
    )
    missing = [decl for name, decl in declarations
               if not re.search(rf"\b{re.escape(name)}\b", text, re.I)]
    if missing:
        anchor = re.search(r"^\s*real\s*::\s*cd_t2_off\b[^\n]*$", text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cd_t2_off module declaration anchor not found")
        replacement = anchor.group(0) + "\n" + "\n".join(missing)
        text = text[:anchor.start()] + replacement + text[anchor.end():]
    if text != before:
        modules.write_text(text)
        return True
    return False


def _ensure_input_vars() -> bool:
    inputf = native.SRC / "unstructured/input.f90"
    text = inputf.read_text()
    before = text

    regs = (
        '  call add_var_double("W_cd2", W_cd2, 0., &\n'
        '       "second-window center-profile width", source_grp)\n'
        '  call add_var_double("W_cd2_shoulder", W_cd2_shoulder, 0., &\n'
        '       "second-window shoulder width", source_grp)\n'
        '  call add_var_double("delta_cd2", delta_cd2, 0., &\n'
        '       "second-window shoulder separation", source_grp)\n'
    )

    if '"W_cd2"' not in text:
        anchor = re.search(
            r'(?mi)^[ \t]*call[ \t]+add_var_double\("cd_t2_off"'
            r'[^\n]*&[ \t]*\n[ \t]*[^\n]*source_grp\)[ \t]*$',
            text,
        )
        if not anchor:
            raise RuntimeError("complete cd_t2_off input registration anchor not found")
        insert_at = anchor.end()
        text = text[:insert_at] + "\n" + regs.rstrip("\n") + text[insert_at:]

    for var in ("W_cd2", "W_cd2_shoulder", "delta_cd2"):
        count = len(re.findall(
            rf'(?mi)^[ \t]*call[ \t]+add_var_double\("{re.escape(var)}"',
            text,
        ))
        if count != 1:
            raise RuntimeError(f"{var} registration count {count}, expected 1")

    if text != before:
        inputf.write_text(text)
        return True
    return False


def install_two_profile_operator() -> bool:
    transport = native.SRC / "unstructured/transport.f90"
    existing = transport.read_text()

    if MARKER in existing:
        module_changed = _ensure_module_vars()
        input_changed = _ensure_input_vars()
        return bool(module_changed or input_changed)

    changed = repair.repaired_install_native_two_window_operator()
    changed = _ensure_module_vars() or changed
    changed = _ensure_input_vars() or changed

    text = transport.read_text()
    pattern = re.compile(
        r"temp79a\s*=\s*\(cd_gate\s*\*\s*J_0cd\s*\+\s*cd_gate2\s*\*\s*J_0cd2\)"
        r"\s*\*\s*temp79a\s*\n\s*temp\s*=\s*temp\s*\+\s*intx2\(mu79\(:,:,OP_1\),temp79a\)",
        re.I,
    )
    m = pattern.search(text)
    if not m:
        raise RuntimeError("combined two-window amplitude application anchor not found")

    new = """temp79a = cd_gate * J_0cd * temp79a
     temp = temp + intx2(mu79(:,:,OP_1),temp79a)

     ! TCT two-profile second-window spatial profile
     if(W_cd2.gt.0.) then
        cd_w_center = W_cd2
     else
        cd_w_center = max(W_cd, 1.e-30)
     end if
     if(W_cd2_shoulder.gt.0.) then
        cd_w_sh = W_cd2_shoulder
     else if(W_cd_shoulder.gt.0.) then
        cd_w_sh = W_cd_shoulder
     else
        cd_w_sh = cd_w_center
     end if
     cd_sep = abs(delta_cd2)
     temp79a = 0.
     temp79b = 0.
     do j=1,npoints
        call magnetic_region(pst79(j,OP_1),pst79(j,OP_DR),pst79(j,OP_DZ), &
             x_79(j),z_79(j),iregion)
        if(iregion.eq.REGION_PLASMA) then
           temp79a(j) = -exp( -(x_79(j)-R_0cd)**2/cd_w_center**2 &
                - (z_79(j)-Z_0cd)**2/cd_w_center**2 ) &
                + 0.5*exp( -(x_79(j)-R_0cd)**2/cd_w_sh**2 &
                - (z_79(j)-(Z_0cd-cd_sep))**2/cd_w_sh**2 ) &
                + 0.5*exp( -(x_79(j)-R_0cd)**2/cd_w_sh**2 &
                - (z_79(j)-(Z_0cd+cd_sep))**2/cd_w_sh**2 )
           temp79b(j) = 1.
        end if
     enddo
     cd_area = real(int1(temp79b))
     if(cd_area.gt.0.) then
        cd_net = real(int1(temp79a))/cd_area
        do j=1,npoints
           if(real(temp79b(j)).gt.0.) temp79a(j) = temp79a(j) - cd_net
        enddo
     end if
     temp79a = cd_gate2 * J_0cd2 * temp79a
     temp = temp + intx2(mu79(:,:,OP_1),temp79a)"""

    text = text[:m.start()] + new + text[m.end():]
    transport.write_text(text)
    return True


def patch_second_profile(d: Path, width: float, shoulder_width: float, delta: float) -> None:
    path = d / "C1input"
    text = path.read_text()
    for key, value in {
        "W_cd2": f"{width:.10g}",
        "W_cd2_shoulder": f"{shoulder_width:.10g}",
        "delta_cd2": f"{delta:.10g}",
    }.items():
        text = pta.replace_or_add(text, key, value)
    path.write_text(text)


def run_case(label: str, *, source: int, amp1: float, t1_on: float, t1_off: float,
             amp2: float, t2_on: float, t2_off: float, second_width: float,
             second_shoulder_width: float, second_delta: float):
    d = native.prepare_run(label, source, amp1, t1_on, t1_off, amp2, t2_on, t2_off)
    patch_second_profile(d, second_width, second_shoulder_width, second_delta)
    print(
        f"[native-two-profile] {label} "
        f"first={amp1:.4f}@{t1_on:.2f}->{t1_off:.2f} "
        f"P1=({PROFILE_WIDTH:.4f},{FIRST_SHOULDER_WIDTH:.4f},{FIRST_DELTA:.4f}) "
        f"second={amp2:.4f}@{t2_on:.2f}->{t2_off:.2f} "
        f"P2=({second_width:.4f},{second_shoulder_width:.4f},{second_delta:.4f})",
        flush=True,
    )
    status = native.execute(d)
    rows = pta.extract(d)
    native.nearest(rows, HORIZON)
    return d, rows, status


def trajectory_equivalence(a_rows, b_rows, tol: float = EQ_TOL) -> dict:
    checks = []
    passed = True
    for t in native.all_times(a_rows):
        a = native.nearest(a_rows, t)
        b = native.nearest(b_rows, t)
        by_metric = {}
        for key in native.METRICS:
            delta = float(b[key]) - float(a[key])
            ok = abs(delta) <= tol
            passed = passed and ok
            by_metric[key] = {"delta": delta, "pass": ok}
        checks.append({"time": t, "by_metric": by_metric})
    return {"tolerance": tol, "pass": passed, "checks": checks}


def label_for(handoff: float, sw: float, delta: float) -> str:
    h = f"{handoff:.2f}".replace(".", "p")
    s = f"{sw:.4f}".replace(".", "p")
    d = f"{delta:.4f}".replace(".", "p")
    return f"two_profile_h{h}_sw{s}_d{d}"


def summarize(label, handoff, sw2, delta2, rows, baseline_rows):
    s = native.summarize_case(label=label, second_start=handoff, second_amp=AMP,
                              rows=rows, baseline_rows=baseline_rows)
    s.update({
        "kind": "uninterrupted_native_two_profile_handoff",
        "first_start": START,
        "first_stop": handoff,
        "first_amp": AMP,
        "first_profile_width": PROFILE_WIDTH,
        "first_shoulder_width": FIRST_SHOULDER_WIDTH,
        "first_shoulder_delta": FIRST_DELTA,
        "second_start": handoff,
        "second_stop": HORIZON,
        "second_amp": AMP,
        "second_profile_width": PROFILE_WIDTH,
        "second_shoulder_width": sw2,
        "second_shoulder_delta": delta2,
    })
    by_time = {round(float(r["time"]), 8): r for r in s["all_step_samples"]}
    for t in (0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.20, 0.25, 0.30):
        r = by_time.get(round(t, 8))
        if r:
            p = f"t{t:.2f}".replace(".", "p")
            s[f"{p}_width_gain_pct"] = r["width_gain_pct"]
            s[f"{p}_Jpk_change_pct"] = r["Jpk_change_pct"]
            s[f"{p}_high_J_change_pct"] = r["high_J_change_pct"]
    return s


def main() -> int:
    if not native.BASE.exists():
        raise FileNotFoundError(native.BASE)
    if not native.EXE.exists():
        raise FileNotFoundError(native.EXE)

    native.OUT = OUT
    native.RUN_ROOT = RUN_ROOT
    native.PROFILE_WIDTH = PROFILE_WIDTH
    native.SHOULDER_WIDTH = FIRST_SHOULDER_WIDTH
    native.SHOULDER_DELTA = FIRST_DELTA
    native.SECOND_STOP = HORIZON

    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    pta.install_operator()
    install_two_profile_operator()
    pta.build()

    baseline_dir, baseline_rows, baseline_status = run_case(
        "baseline_source0", source=0,
        amp1=0.0, t1_on=0.0, t1_off=HORIZON,
        amp2=0.0, t2_on=HORIZON, t2_off=HORIZON,
        second_width=PROFILE_WIDTH, second_shoulder_width=FIRST_SHOULDER_WIDTH,
        second_delta=FIRST_DELTA)

    zero_dir, zero_rows, zero_status = run_case(
        "source4_zero", source=native.CURRENT_SOURCE,
        amp1=0.0, t1_on=START, t1_off=0.13,
        amp2=0.0, t2_on=0.13, t2_off=HORIZON,
        second_width=PROFILE_WIDTH, second_shoulder_width=0.40,
        second_delta=0.30)
    zero_check = native.zero_equivalence(baseline_rows, zero_rows)

    ref_dir, ref_rows, ref_status = run_case(
        "constant_profile_reference", source=native.CURRENT_SOURCE,
        amp1=AMP, t1_on=START, t1_off=HORIZON,
        amp2=0.0, t2_on=HORIZON, t2_off=HORIZON,
        second_width=PROFILE_WIDTH, second_shoulder_width=FIRST_SHOULDER_WIDTH,
        second_delta=FIRST_DELTA)

    eq_dir, eq_rows, eq_status = run_case(
        "same_profile_handoff_equivalence", source=native.CURRENT_SOURCE,
        amp1=AMP, t1_on=START, t1_off=0.13,
        amp2=AMP, t2_on=0.13, t2_off=HORIZON,
        second_width=PROFILE_WIDTH, second_shoulder_width=FIRST_SHOULDER_WIDTH,
        second_delta=FIRST_DELTA)
    handoff_equivalence = trajectory_equivalence(ref_rows, eq_rows)

    summaries = []
    executions = []
    flat_rows = []
    for handoff in HANDOFF_TIMES:
        for sw2 in SECOND_SHOULDER_WIDTHS:
            for delta2 in SECOND_DELTAS:
                label = label_for(handoff, sw2, delta2)
                d, rows, status = run_case(
                    label, source=native.CURRENT_SOURCE,
                    amp1=AMP, t1_on=START, t1_off=handoff,
                    amp2=AMP, t2_on=handoff, t2_off=HORIZON,
                    second_width=PROFILE_WIDTH, second_shoulder_width=sw2,
                    second_delta=delta2)
                s = summarize(label, handoff, sw2, delta2, rows, baseline_rows)
                s["directory"] = str(d)
                summaries.append(s)
                executions.append({
                    "case": label, "handoff_time": handoff,
                    "second_shoulder_width": sw2,
                    "second_shoulder_delta": delta2,
                    "directory": str(d), "return_code": status["return_code"],
                })
                flat_rows.extend({
                    "case": label, "handoff_time": handoff,
                    "second_shoulder_width": sw2,
                    "second_shoulder_delta": delta2, **row,
                } for row in s["all_step_samples"])

    ranked = sorted(summaries, key=lambda s: (
        bool(s["sustained_safe_authority"]),
        bool(s["current_gate_pass_every_step_t0p10_to_t0p30"]),
        bool(s["continuous_positive_width_t0p10_to_t0p30"]),
        bool(s["final_width_gate_pass"]),
        float(s["minimum_width_gain_pct"]),
        -max(0.0, float(s["worst_Jpk_change_pct"]) - native.JPK_GATE_PCT),
        float(s["final_width_gain_pct"]),
        float(s["peak_width_gain_pct"]),
    ), reverse=True)
    sustained = [s["case"] for s in ranked if s["sustained_safe_authority"]]
    current_safe = [s["case"] for s in ranked
                    if s["current_gate_pass_every_step_t0p10_to_t0p30"]]

    if not zero_check["pass"]:
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_ZERO_EQUIVALENCE_FAILED"
    elif not handoff_equivalence["pass"]:
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_HANDOFF_EQUIVALENCE_FAILED"
    elif sustained:
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_SUSTAINED_SAFE_AUTHORITY"
    elif current_safe:
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_CURRENT_SAFE_TRANSIENT_AUTHORITY"
    elif any(s["width_gate_pass_any"] for s in ranked):
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_NATIVE_TWO_PROFILE_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "sustained_pass_count": len(sustained),
        "sustained_pass_cases": sustained,
        "current_safe_count": len(current_safe),
        "current_safe_cases": current_safe,
        "zero_equivalence": zero_check,
        "handoff_equivalence": handoff_equivalence,
        "claim_boundary": (
            "Normalized native M3D-C1 uninterrupted two-profile handoff audit only. "
            "Frozen +0.020% width and +0.10% Jpk gates are unchanged and evaluated "
            "at every dt=0.01 sample from t=0.10 through t=0.30. No restart is used. "
            "No reactor-scale or experimental stabilization claim is implied."
        ),
        "audit": {
            "type": "uninterrupted_native_two_profile_handoff",
            "reason": (
                "static shoulder geometry improved the joint Jpk/width frontier but "
                "could not keep width positive through t=0.14-0.16; this audit changes "
                "the spatial redistribution profile before that excursion"
            ),
            "dt": native.DT, "horizon": HORIZON, "start": START,
            "amplitude": AMP,
            "first_profile": {
                "center_width": PROFILE_WIDTH,
                "shoulder_width": FIRST_SHOULDER_WIDTH,
                "shoulder_delta": FIRST_DELTA,
            },
            "handoff_times": list(HANDOFF_TIMES),
            "second_profile_center_width": PROFILE_WIDTH,
            "second_shoulder_widths": list(SECOND_SHOULDER_WIDTHS),
            "second_shoulder_deltas": list(SECOND_DELTAS),
            "frozen_gates": {
                "width_gain_pct_gt": native.WIDTH_GATE_PCT,
                "Jpk_change_pct_le": native.JPK_GATE_PCT,
            },
            "restart_used_for_switching": False,
        },
        "baseline": {"directory": str(baseline_dir), "execution": baseline_status},
        "source4_zero": {"directory": str(zero_dir), "execution": zero_status},
        "constant_profile_reference": {"directory": str(ref_dir), "execution": ref_status},
        "same_profile_handoff": {"directory": str(eq_dir), "execution": eq_status},
        "best_case": ranked[0] if ranked else None,
        "case_summaries": ranked,
        "executions": executions,
    }

    write_json(OUT / "native_two_profile_handoff_summary.json", report)
    pta.write_csv(OUT / "native_two_profile_handoff_samples.csv", flat_rows)
    pta.write_csv(OUT / "native_two_profile_handoff_case_summary.csv", [
        {key: s[key] for key in (
            "case", "first_profile_width", "first_shoulder_width",
            "first_shoulder_delta", "second_profile_width",
            "second_shoulder_width", "second_shoulder_delta",
            "second_start", "sustained_safe_authority",
            "continuous_positive_width_t0p10_to_t0p30",
            "current_gate_pass_every_step_t0p10_to_t0p30",
            "width_gate_pass_any", "final_width_gate_pass",
            "minimum_width_gain_pct", "minimum_width_time",
            "peak_width_gain_pct", "peak_width_time",
            "worst_Jpk_change_pct", "worst_Jpk_time",
            "Jpk_guard_margin_pct", "final_width_gain_pct",
            "final_Jpk_change_pct", "max_high_J_change_pct",
            "max_high_J_time")}
        for s in ranked])
    (OUT / "runtime_provenance.txt").write_text("\n".join([
        f"repo={REPO}", f"source={native.SRC}", f"baseline={native.BASE}",
        f"executable={native.EXE}",
        f"executable_sha256={pta.sha256_file(native.EXE)}",
        f"run_root={RUN_ROOT}", f"dt={native.DT}", f"horizon={HORIZON}",
        f"start={START}", f"amplitude={AMP}",
        f"first_profile=({PROFILE_WIDTH},{FIRST_SHOULDER_WIDTH},{FIRST_DELTA})",
        f"handoff_times={list(HANDOFF_TIMES)}",
        f"second_profile_center_width={PROFILE_WIDTH}",
        f"second_shoulder_widths={list(SECOND_SHOULDER_WIDTHS)}",
        f"second_shoulder_deltas={list(SECOND_DELTAS)}",
        f"zero_equivalence_tol={native.ZERO_ABS_TOL}",
        f"handoff_equivalence_tol={EQ_TOL}",
        f"width_gate_pct={native.WIDTH_GATE_PCT}",
        f"jpk_gate_pct={native.JPK_GATE_PCT}",
        "acceptance=every native step from 0.10 through 0.30",
        "switching=uninterrupted two spatial profiles; no restart boundaries", ""]))

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if zero_check["pass"] and handoff_equivalence["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
