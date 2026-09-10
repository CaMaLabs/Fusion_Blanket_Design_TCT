#!/usr/bin/env python3
"""Uninterrupted native two-window TCT current-drive refinement audit.

This audit exists because the paired-restart refinement showed a common failure
immediately after the t=0.15 restart boundary. Here both current-drive windows
are represented inside one uninterrupted native M3D-C1 run, so no restart is
used to switch the actuator.

Frozen acceptance gates:
  * every native dt=0.01 sample from t=0.10 through 0.30 has width_gain_pct > 0
  * every native sample over that interval has Jpk_change_pct <= +0.10
  * at least one native sample exceeds +0.020% width
  * final t=0.30 width_gain_pct exceeds +0.020%

A source=4 zero-amplitude run is checked against source=0 to verify that the
extended operator is inert when both window amplitudes are zero.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import time
from pathlib import Path

import native_feedback_controller_audit as nfc
import pulse_train_audit as pta

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_native_two_window_sustained_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_two_window_sustained_refinement_runs")

DT = 0.01
HORIZON = 0.30
HORIZON_STEPS = 30
FIRST_START = 0.05
FIRST_STOP = 0.15
FIRST_AMP = -0.030
SECOND_STARTS = (0.16, 0.17, 0.18, 0.19)
SECOND_AMPS = (-0.020, -0.025, -0.030)
SECOND_STOP = 0.30

CURRENT_SOURCE = 4
PROFILE_WIDTH = 0.1375
SHOULDER_WIDTH = 0.2805
SHOULDER_DELTA = 0.561
R0 = 10.0
Z0 = 1.0

WIDTH_GATE_PCT = 0.020
JPK_GATE_PCT = 0.10
ZERO_ABS_TOL = 1e-12
TIME_TOL = 1e-8

METRICS = (
    "W_sheet",
    "Jpk",
    "Jint_high",
    "center_abs_current",
    "shoulder_abs_current",
    "Reconnected_Flux",
    "magnetic_energy",
)


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


def install_native_two_window_operator() -> bool:
    """Extend the validated source=4 operator with a second native time window."""
    nfc.install_current_redistribution_operator()

    modules = SRC / "unstructured/M3Dmodules.f90"
    inputf = SRC / "unstructured/input.f90"
    transport = SRC / "unstructured/transport.f90"
    for path in (modules, inputf, transport):
        if not path.exists():
            raise FileNotFoundError(path)

    changed = False

    text = modules.read_text()
    declarations = {
        "j_0cd2": "  real :: J_0cd2       ! amplitude of second current-drive window",
        "cd_t2_on": "  real :: cd_t2_on      ! second current-drive turn-on time",
        "cd_t2_off": "  real :: cd_t2_off     ! second current-drive turn-off time",
    }
    missing = [
        declaration
        for name, declaration in declarations.items()
        if not re.search(rf"\b{re.escape(name)}\b", text, re.I)
    ]
    if missing:
        anchor = re.search(r"^\s*real\s*::\s*cd_t_off\b[^\n]*$", text, re.I | re.M)
        if not anchor:
            raise RuntimeError("cd_t_off module declaration anchor not found")
        addition = anchor.group(0) + "\n" + "\n".join(missing)
        text = text[:anchor.start()] + addition + text[anchor.end():]
        modules.write_text(text)
        changed = True

    text = inputf.read_text()
    if '"J_0cd2"' not in text:
        anchor = re.search(
            r'^\s*call\s+add_var_double\("cd_t_off"[^\n]*\n(?:[^\n]*\n){0,2}',
            text,
            re.I | re.M,
        )
        if not anchor:
            raise RuntimeError("cd_t_off input registration anchor not found")
        regs = anchor.group(0) + (
            '  call add_var_double("J_0cd2", J_0cd2, 0., &\n'
            '       "second-window current-drive amplitude", source_grp)\n'
            '  call add_var_double("cd_t2_on", cd_t2_on, 1.e30, &\n'
            '       "second current-drive turn-on time", source_grp)\n'
            '  call add_var_double("cd_t2_off", cd_t2_off, 1.e30, &\n'
            '       "second current-drive turn-off time", source_grp)\n'
        )
        text = text[:anchor.start()] + regs + text[anchor.end():]
        inputf.write_text(text)
        changed = True

    text = transport.read_text()
    start = text.find("function cd_func")
    end = text.find("cd_func = temp", start)
    if start < 0 or end < 0:
        raise RuntimeError("cd_func source block not found")
    func = text[start:end]

    if not re.search(r"\bcd_gate2\b", func, re.I):
        local_anchor = re.search(
            r"^\s*real\s*::\s*cd_gate,\s*cd_tau,\s*cd_w_center,\s*cd_w_sh,\s*cd_sep\s*$",
            func,
            re.I | re.M,
        )
        if not local_anchor:
            raise RuntimeError("cd_func gate local declaration anchor not found")
        replacement = local_anchor.group(0).replace("cd_gate,", "cd_gate, cd_gate2,")
        absolute_start = start + local_anchor.start()
        absolute_end = start + local_anchor.end()
        text = text[:absolute_start] + replacement + text[absolute_end:]
        changed = True
        end += len(replacement) - len(local_anchor.group(0))
        func = text[start:end]

    if "cd_t2_on" not in func:
        gate_anchor = re.search(
            r"(?ms)^\s*if\(time\.lt\.cd_t_on.*?^\s*end if\s*$",
            func,
        )
        if not gate_anchor:
            raise RuntimeError("primary cd_gate block not found")
        gate2 = (
            "\n  if(time.lt.cd_t2_on .or. time.ge.cd_t2_off) then\n"
            "     cd_gate2 = 0.\n"
            "  else\n"
            "     cd_gate2 = 1.\n"
            "  end if"
        )
        insert_at = start + gate_anchor.end()
        text = text[:insert_at] + gate2 + text[insert_at:]
        changed = True
        end += len(gate2)
        func = text[start:end]

    old = "temp79a = cd_gate * J_0cd * temp79a"
    new = "temp79a = (cd_gate * J_0cd + cd_gate2 * J_0cd2) * temp79a"
    if old in func:
        absolute = start + func.index(old)
        text = text[:absolute] + new + text[absolute + len(old):]
        changed = True
    elif new not in func:
        raise RuntimeError("source=4 amplitude application anchor not found")

    if changed:
        transport.write_text(text)

    return changed


def prepare_run(
    name: str,
    source: int,
    amp1: float,
    t1_on: float,
    t1_off: float,
    amp2: float,
    t2_on: float,
    t2_off: float,
) -> Path:
    d = RUN_ROOT / name
    remove(d)
    d.mkdir(parents=True)

    for item in pta.COPY_NAMES:
        src = BASE / item
        if src.is_symlink():
            (d / item).symlink_to(src.readlink())
        elif src.exists():
            shutil.copy2(src, d / item)

    text = (BASE / "C1input").read_text()
    updates = {
        "dt": f"{DT:.10g}",
        "ntimemax": str(HORIZON_STEPS),
        "ntimepr": "1",
        "irestart": "0",
        "irestart_slice": "-1",
        "iwrite_restart": "0",
        "imag_control": "0",
        "mag_ctrl_amp": "0.0",
        "icd_source": str(source),
        "J_0cd": f"{amp1:.10g}",
        "R_0cd": f"{R0:.10g}",
        "Z_0cd": f"{Z0:.10g}",
        "W_cd": f"{PROFILE_WIDTH:.10g}",
        "W_cd_shoulder": f"{SHOULDER_WIDTH:.10g}",
        "delta_cd": f"{SHOULDER_DELTA:.10g}",
        "cd_t_on": f"{t1_on:.10g}",
        "cd_t_ramp": "0.0",
        "cd_t_off": f"{t1_off:.10g}",
        "J_0cd2": f"{amp2:.10g}",
        "cd_t2_on": f"{t2_on:.10g}",
        "cd_t2_off": f"{t2_off:.10g}",
    }
    for key, value in updates.items():
        text = pta.replace_or_add(text, key, value)
    (d / "C1input").write_text(text)

    launcher = f"""#!/usr/bin/env bash
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
"""
    (d / "launch_command.sh").write_text(launcher)
    (d / "launch_command.sh").chmod(0o755)
    return d


def execute(d: Path) -> dict:
    t0 = time.time()
    p = pta.sh(["bash", "launch_command.sh"], cwd=d)
    status = {
        "return_code": p.returncode,
        "elapsed_seconds": time.time() - t0,
        "wrapper_tail": p.stdout[-3000:],
        "C1stdout_tail": (
            (d / "C1stdout").read_text(errors="replace")[-5000:]
            if (d / "C1stdout").exists()
            else ""
        ),
        "launcher_stderr_tail": (
            (d / "launcher.stderr").read_text(errors="replace")[-5000:]
            if (d / "launcher.stderr").exists()
            else ""
        ),
    }
    write_json(d / "run_status.json", status)
    if p.returncode:
        raise RuntimeError(
            f"{d.name} failed rc={p.returncode}\n"
            f"{status['C1stdout_tail']}\n{status['launcher_stderr_tail']}"
        )
    return status


def nearest(rows: list[dict[str, float]], t: float) -> dict[str, float]:
    if not rows:
        raise RuntimeError("no extracted rows")
    row = min(rows, key=lambda r: abs(float(r["time"]) - t))
    if abs(float(row["time"]) - t) > TIME_TOL:
        raise RuntimeError(f"missing t={t}; nearest={row['time']}")
    return row


def pct(value: float, baseline: float) -> float:
    if abs(baseline) <= 1e-300:
        return math.nan
    return 100.0 * (value / baseline - 1.0)


def compare_row(control: dict[str, float], baseline: dict[str, float]) -> dict:
    width = pct(float(control["W_sheet"]), float(baseline["W_sheet"]))
    jpk = pct(float(control["Jpk"]), float(baseline["Jpk"]))
    return {
        "time": float(control["time"]),
        "width_gain_pct": width,
        "Jpk_change_pct": jpk,
        "high_J_change_pct": pct(
            float(control["Jint_high"]), float(baseline["Jint_high"])
        ),
        "baseline_Jint_high": float(baseline["Jint_high"]),
        "controlled_Jint_high": float(control["Jint_high"]),
        "delta_Jint_high_abs": (
            float(control["Jint_high"]) - float(baseline["Jint_high"])
        ),
        "center_change_pct": pct(
            float(control["center_abs_current"]),
            float(baseline["center_abs_current"]),
        ),
        "shoulder_change_pct": pct(
            float(control["shoulder_abs_current"]),
            float(baseline["shoulder_abs_current"]),
        ),
        "delta_Reconnected_Flux": (
            float(control["Reconnected_Flux"]) - float(baseline["Reconnected_Flux"])
        ),
        "delta_magnetic_energy": (
            float(control["magnetic_energy"]) - float(baseline["magnetic_energy"])
        ),
        "width_gate_pass": width > WIDTH_GATE_PCT,
        "current_gate_pass": jpk <= JPK_GATE_PCT,
    }


def all_times(rows: list[dict[str, float]]) -> list[float]:
    return sorted(
        float(r["time"])
        for r in rows
        if 0.10 - TIME_TOL <= float(r["time"]) <= HORIZON + TIME_TOL
    )


def zero_equivalence(
    baseline_rows: list[dict[str, float]],
    zero_rows: list[dict[str, float]],
) -> dict:
    checks = []
    all_pass = True
    for t in all_times(baseline_rows):
        brow = nearest(baseline_rows, t)
        zrow = nearest(zero_rows, t)
        by_metric = {}
        for key in METRICS:
            delta = float(zrow[key]) - float(brow[key])
            passed = abs(delta) <= ZERO_ABS_TOL
            by_metric[key] = {"delta": delta, "pass": passed}
            all_pass = all_pass and passed
        checks.append({"time": t, "by_metric": by_metric})
    return {
        "tolerance": ZERO_ABS_TOL,
        "pass": all_pass,
        "checks": checks,
    }


def summarize_case(
    label: str,
    second_start: float,
    second_amp: float,
    rows: list[dict[str, float]],
    baseline_rows: list[dict[str, float]],
) -> dict:
    sample_times = all_times(baseline_rows)
    samples = [
        compare_row(nearest(rows, t), nearest(baseline_rows, t))
        for t in sample_times
    ]
    if not samples or abs(float(samples[-1]["time"]) - HORIZON) > TIME_TOL:
        raise RuntimeError(f"{label}: incomplete native trajectory")

    positive_every = all(float(r["width_gain_pct"]) > 0.0 for r in samples)
    current_safe_every = all(float(r["Jpk_change_pct"]) <= JPK_GATE_PCT for r in samples)
    width_gate_any = any(float(r["width_gain_pct"]) > WIDTH_GATE_PCT for r in samples)
    final = samples[-1]
    final_width_gate = float(final["width_gain_pct"]) > WIDTH_GATE_PCT
    sustained = positive_every and current_safe_every and width_gate_any and final_width_gate

    minimum = min(samples, key=lambda r: float(r["width_gain_pct"]))
    peak = max(samples, key=lambda r: float(r["width_gain_pct"]))
    worst_jpk = max(samples, key=lambda r: float(r["Jpk_change_pct"]))
    max_high_j = max(samples, key=lambda r: float(r["high_J_change_pct"]))
    min_high_j = min(samples, key=lambda r: float(r["high_J_change_pct"]))

    return {
        "case": label,
        "kind": "uninterrupted_native_two_window_sustained_refinement",
        "first_start": FIRST_START,
        "first_stop": FIRST_STOP,
        "first_amp": FIRST_AMP,
        "second_start": second_start,
        "second_stop": SECOND_STOP,
        "second_amp": second_amp,
        "sustained_safe_authority": sustained,
        "continuous_positive_width_t0p10_to_t0p30": positive_every,
        "current_gate_pass_every_step_t0p10_to_t0p30": current_safe_every,
        "width_gate_pass_any": width_gate_any,
        "final_width_gate_pass": final_width_gate,
        "minimum_width_gain_pct": minimum["width_gain_pct"],
        "minimum_width_time": minimum["time"],
        "positive_width_margin_pct": minimum["width_gain_pct"],
        "peak_width_gain_pct": peak["width_gain_pct"],
        "peak_width_time": peak["time"],
        "worst_Jpk_change_pct": worst_jpk["Jpk_change_pct"],
        "worst_Jpk_time": worst_jpk["time"],
        "Jpk_guard_margin_pct": JPK_GATE_PCT - float(worst_jpk["Jpk_change_pct"]),
        "final_width_gain_pct": final["width_gain_pct"],
        "final_Jpk_change_pct": final["Jpk_change_pct"],
        "max_high_J_change_pct": max_high_j["high_J_change_pct"],
        "max_high_J_time": max_high_j["time"],
        "min_high_J_change_pct": min_high_j["high_J_change_pct"],
        "all_step_samples": samples,
    }


def run_case(
    label: str,
    source: int,
    amp1: float,
    t1_on: float,
    t1_off: float,
    amp2: float,
    t2_on: float,
    t2_off: float,
) -> tuple[Path, list[dict[str, float]], dict]:
    d = prepare_run(label, source, amp1, t1_on, t1_off, amp2, t2_on, t2_off)
    print(
        f"[native-two-window] {label} "
        f"first={amp1:.4f}@{t1_on:.2f}->{t1_off:.2f} "
        f"second={amp2:.4f}@{t2_on:.2f}->{t2_off:.2f}",
        flush=True,
    )
    status = execute(d)
    rows = pta.extract(d)
    nearest(rows, HORIZON)
    return d, rows, status


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    pta.install_operator()
    install_native_two_window_operator()
    pta.build()

    baseline_dir, baseline_rows, baseline_status = run_case(
        "baseline_source0",
        source=0,
        amp1=0.0,
        t1_on=0.0,
        t1_off=HORIZON,
        amp2=0.0,
        t2_on=HORIZON,
        t2_off=HORIZON,
    )
    zero_dir, zero_rows, zero_status = run_case(
        "source4_zero",
        source=CURRENT_SOURCE,
        amp1=0.0,
        t1_on=FIRST_START,
        t1_off=FIRST_STOP,
        amp2=0.0,
        t2_on=min(SECOND_STARTS),
        t2_off=SECOND_STOP,
    )
    zero_check = zero_equivalence(baseline_rows, zero_rows)

    summaries = []
    flat_rows = []
    executions = []
    for second_start in SECOND_STARTS:
        for second_amp in SECOND_AMPS:
            label = (
                f"native2_s{second_start:.2f}_a{abs(second_amp):.3f}"
                .replace(".", "p")
            )
            d, rows, status = run_case(
                label,
                source=CURRENT_SOURCE,
                amp1=FIRST_AMP,
                t1_on=FIRST_START,
                t1_off=FIRST_STOP,
                amp2=second_amp,
                t2_on=second_start,
                t2_off=SECOND_STOP,
            )
            summary = summarize_case(
                label, second_start, second_amp, rows, baseline_rows
            )
            summary["directory"] = str(d)
            summaries.append(summary)
            executions.append(
                {
                    "case": label,
                    "directory": str(d),
                    "return_code": status["return_code"],
                }
            )
            flat_rows.extend({"case": label, **r} for r in summary["all_step_samples"])

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["sustained_safe_authority"]),
            bool(s["current_gate_pass_every_step_t0p10_to_t0p30"]),
            bool(s["continuous_positive_width_t0p10_to_t0p30"]),
            float(s["final_width_gain_pct"]),
            float(s["minimum_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    sustained = [s["case"] for s in ranked if s["sustained_safe_authority"]]

    if not zero_check["pass"]:
        classification = "M3DC1_TCT_NATIVE_TWO_WINDOW_ZERO_EQUIVALENCE_FAILED"
    elif sustained:
        classification = "M3DC1_TCT_NATIVE_TWO_WINDOW_SUSTAINED_SAFE_AUTHORITY"
    elif any(s["width_gate_pass_any"] for s in ranked):
        classification = "M3DC1_TCT_NATIVE_TWO_WINDOW_TRANSIENT_SAFE_AUTHORITY"
    else:
        classification = "M3DC1_TCT_NATIVE_TWO_WINDOW_NO_SAFE_AUTHORITY_FOUND"

    report = {
        "classification": classification,
        "sustained_pass_count": len(sustained),
        "sustained_pass_cases": sustained,
        "claim_boundary": (
            "Normalized native M3D-C1 uninterrupted two-window current-drive audit only. "
            "Frozen +0.020% width and +0.10% Jpk gates are unchanged. No restart is used "
            "to switch either actuator window. Acceptance is evaluated at every dt=0.01 "
            "sample from t=0.10 through t=0.30. No reactor-scale or experimental "
            "stabilization claim is implied."
        ),
        "audit": {
            "type": "uninterrupted_native_two_window_sustained_refinement",
            "reason": (
                "paired-restart refinement showed a common t=0.16 failure immediately "
                "after the t=0.15 restart boundary; this audit removes that boundary"
            ),
            "dt": DT,
            "horizon": HORIZON,
            "first_window": [FIRST_START, FIRST_STOP, FIRST_AMP],
            "second_starts": list(SECOND_STARTS),
            "second_amps": list(SECOND_AMPS),
            "second_stop": SECOND_STOP,
            "profile_width": PROFILE_WIDTH,
            "frozen_gates": {
                "width_gain_pct_gt": WIDTH_GATE_PCT,
                "Jpk_change_pct_le": JPK_GATE_PCT,
            },
            "acceptance": {
                "continuous_positive_width_t0p10_to_t0p30": True,
                "current_gate_every_step_t0p10_to_t0p30": True,
                "width_gate_pass_any": True,
                "final_width_gate_pass": True,
            },
            "restart_used_for_switching": False,
        },
        "zero_equivalence": zero_check,
        "baseline": {
            "directory": str(baseline_dir),
            "execution": baseline_status,
        },
        "source4_zero": {
            "directory": str(zero_dir),
            "execution": zero_status,
        },
        "best_case": ranked[0] if ranked else None,
        "case_summaries": ranked,
        "executions": executions,
    }

    write_json(OUT / "native_two_window_refinement_summary.json", report)
    pta.write_csv(OUT / "native_two_window_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "native_two_window_case_summary.csv",
        [
            {
                key: s[key]
                for key in (
                    "case",
                    "second_start",
                    "second_amp",
                    "sustained_safe_authority",
                    "continuous_positive_width_t0p10_to_t0p30",
                    "current_gate_pass_every_step_t0p10_to_t0p30",
                    "width_gate_pass_any",
                    "final_width_gate_pass",
                    "minimum_width_gain_pct",
                    "minimum_width_time",
                    "peak_width_gain_pct",
                    "peak_width_time",
                    "worst_Jpk_change_pct",
                    "worst_Jpk_time",
                    "Jpk_guard_margin_pct",
                    "final_width_gain_pct",
                    "final_Jpk_change_pct",
                    "max_high_J_change_pct",
                    "max_high_J_time",
                )
            }
            for s in ranked
        ],
    )
    (OUT / "runtime_provenance.txt").write_text(
        "\n".join(
            [
                f"repo={REPO}",
                f"source={SRC}",
                f"baseline={BASE}",
                f"executable={EXE}",
                f"executable_sha256={pta.sha256_file(EXE)}",
                f"run_root={RUN_ROOT}",
                f"dt={DT}",
                f"horizon={HORIZON}",
                f"profile_width={PROFILE_WIDTH}",
                f"first_pulse={FIRST_START}->{FIRST_STOP}@{FIRST_AMP}",
                f"second_starts={list(SECOND_STARTS)}",
                f"second_amps={list(SECOND_AMPS)}",
                f"second_stop={SECOND_STOP}",
                f"width_gate_pct={WIDTH_GATE_PCT}",
                f"jpk_gate_pct={JPK_GATE_PCT}",
                "acceptance=every native step from 0.10 through 0.30",
                "switching=uninterrupted native two-window operator; no restart boundaries",
                "",
            ]
        )
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if zero_check["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
