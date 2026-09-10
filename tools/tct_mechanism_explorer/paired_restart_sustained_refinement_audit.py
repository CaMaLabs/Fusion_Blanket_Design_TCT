#!/usr/bin/env python3
"""Refine the paired-restart multi_02 schedule for sustained safe authority.

The first pulse is frozen at t=0.05->0.15 with J_0cd=-0.030.  The second pulse
always ends at t=0.30 and sweeps start={0.16,0.17,0.18,0.19} and
amplitude={-0.020,-0.025,-0.030}.  Every controlled branch is compared only
with a source=0 branch that uses the identical restart boundaries.

Acceptance is evaluated at every native dt=0.01 output from t=0.10 through
0.30, not only at sparse report times:
  * width gain > 0 continuously;
  * Jpk change <= +0.10% continuously;
  * width gain > +0.020% at least once;
  * final width gain > +0.020%.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import native_feedback_controller_audit as nfc
import paired_restart_differential_audit as paired
import pulse_train_audit as pta
import restart_transport_audit as rta
import restart_transport_hdf5_repair as h5r

REPO = Path("/home/ubuntu/work/openmc/sweep")
BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
SRC = Path("/home/ubuntu/M3DC1-official")
EXE = SRC / "build-ubuntu-2d/unstructured/m3dc1_2d"
OUT = REPO / "validation_runs/m3dc1_tct_paired_restart_sustained_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_paired_restart_sustained_refinement_runs")

DT = 0.01
HORIZON = 0.30
FULL_EVAL_TIMES = tuple(i * DT for i in range(10, 31))
REPORT_TIMES = (0.10, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.25, 0.30)

CURRENT_SOURCE = 4
PROFILE_WIDTH = 0.1375
FIRST_START = 0.05
FIRST_STOP = 0.15
FIRST_AMP = -0.030
SECOND_STARTS = (0.16, 0.17, 0.18, 0.19)
SECOND_AMPS = (-0.020, -0.025, -0.030)
SECOND_STOP = 0.30

WIDTH_GATE_PCT = 0.020
JPK_GATE_PCT = 0.10
TIME_TOL = 1e-8


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


def configure_base() -> None:
    paired.OUT = OUT
    paired.RUN_ROOT = RUN_ROOT
    paired.DT = DT
    paired.HORIZON = HORIZON
    paired.CURRENT_SOURCE = CURRENT_SOURCE
    paired.PROFILE_WIDTH = PROFILE_WIDTH
    paired.WIDTH_GATE_PCT = WIDTH_GATE_PCT
    paired.JPK_GATE_PCT = JPK_GATE_PCT


def run_segment(
    name: str,
    previous: Path | None,
    source: int,
    amp: float,
    start: float,
    stop: float,
) -> tuple[Path, list[dict[str, float]], dict, dict | None]:
    restart = previous is not None
    d = paired.prepare_dir(name, source, amp, restart, start, stop)
    manifest = h5r.copy_restart(previous, d) if previous is not None else None

    print(
        f"[refine] {name} {start:.2f}->{stop:.2f} "
        f"source={source} amp={amp:.4f} restart={int(restart)}",
        flush=True,
    )
    status = paired.execute(d)
    if status["return_code"]:
        raise RuntimeError(
            f"{name} failed rc={status['return_code']}\n"
            f"C1stdout:\n{status['C1stdout_tail']}\n"
            f"launcher.stderr:\n{status['launcher_stderr_tail']}"
        )

    rows = h5r.extract(d)
    if restart:
        rows = [r for r in rows if float(r["time"]) > start + TIME_TOL]
    if not rows:
        raise RuntimeError(f"{name}: no advanced output")

    last = max(float(r["time"]) for r in rows)
    if abs(last - stop) > TIME_TOL:
        raise RuntimeError(f"{name}: last time {last} != requested stop {stop}")

    return d, rows, status, manifest


def append_history(
    history: list[dict],
    *,
    role: str,
    name: str,
    start: float,
    stop: float,
    source: int,
    amp: float,
    directory: Path,
    status: dict,
    manifest: dict | None,
) -> None:
    history.append(
        {
            "role": role,
            "name": name,
            "start": start,
            "stop": stop,
            "source": source,
            "amp": amp,
            "restart": manifest is not None,
            "directory": str(directory),
            "return_code": status["return_code"],
            "final_C1_sha256": rta.sha256(directory / "C1.h5"),
            "seed_plot": (
                manifest.get("selected_plot_file") if manifest is not None else None
            ),
        }
    )


def eval_rows(
    control_rows: list[dict[str, float]],
    null_rows: list[dict[str, float]],
    uninterrupted_rows: list[dict[str, float]],
) -> list[dict]:
    out: list[dict] = []
    for t in FULL_EVAL_TIMES:
        c = paired.nearest(control_rows, t)
        n = paired.nearest(null_rows, t)
        u = paired.nearest(uninterrupted_rows, t)
        out.append(paired.differential_row(c, n, u))
    return out


def report_rows(full_rows: list[dict]) -> list[dict]:
    return [paired.nearest(full_rows, t) for t in REPORT_TIMES]


def summarize_case(
    label: str,
    second_start: float,
    second_amp: float,
    full_rows: list[dict],
    history: list[dict],
) -> dict:
    if not full_rows:
        raise RuntimeError(f"{label}: no differential rows")

    minimum = min(full_rows, key=lambda r: float(r["width_gain_pct"]))
    maximum = max(full_rows, key=lambda r: float(r["width_gain_pct"]))
    worst_jpk = max(full_rows, key=lambda r: float(r["Jpk_change_pct"]))
    final = paired.nearest(full_rows, HORIZON)

    continuous_positive = all(float(r["width_gain_pct"]) > 0.0 for r in full_rows)
    current_safe_all = all(float(r["Jpk_change_pct"]) <= JPK_GATE_PCT for r in full_rows)
    width_gate_any = any(float(r["width_gain_pct"]) > WIDTH_GATE_PCT for r in full_rows)
    final_width_gate = float(final["width_gain_pct"]) > WIDTH_GATE_PCT
    final_current_safe = float(final["Jpk_change_pct"]) <= JPK_GATE_PCT

    sustained_safe = (
        continuous_positive
        and current_safe_all
        and width_gate_any
        and final_width_gate
        and final_current_safe
    )

    positive_margin = float(minimum["width_gain_pct"])
    jpk_margin = JPK_GATE_PCT - float(worst_jpk["Jpk_change_pct"])
    max_restart_bias = max(
        abs(float(r.get("paired_null_restart_bias_width_pct", 0.0)))
        for r in full_rows
    )
    max_high_j = max(full_rows, key=lambda r: float(r["high_J_change_pct"]))
    min_high_j = min(full_rows, key=lambda r: float(r["high_J_change_pct"]))

    return {
        "case": label,
        "kind": "paired_restart_multi_02_sustained_refinement",
        "windows": [
            [FIRST_START, FIRST_STOP, FIRST_AMP],
            [second_start, SECOND_STOP, second_amp],
        ],
        "second_start": second_start,
        "second_amp": second_amp,
        "continuous_positive_width_t0p10_to_t0p30": continuous_positive,
        "current_gate_pass_every_step_t0p10_to_t0p30": current_safe_all,
        "width_gate_pass_any": width_gate_any,
        "final_width_gate_pass": final_width_gate,
        "final_current_gate_pass": final_current_safe,
        "sustained_safe_authority": sustained_safe,
        "minimum_width_gain_pct": minimum["width_gain_pct"],
        "minimum_width_time": minimum["time"],
        "positive_width_margin_pct": positive_margin,
        "peak_width_gain_pct": maximum["width_gain_pct"],
        "peak_width_time": maximum["time"],
        "worst_Jpk_change_pct": worst_jpk["Jpk_change_pct"],
        "worst_Jpk_time": worst_jpk["time"],
        "Jpk_guard_margin_pct": jpk_margin,
        "final_width_gain_pct": final["width_gain_pct"],
        "final_Jpk_change_pct": final["Jpk_change_pct"],
        "max_high_J_change_pct": max_high_j["high_J_change_pct"],
        "max_high_J_time": max_high_j["time"],
        "min_high_J_change_pct": min_high_j["high_J_change_pct"],
        "max_abs_paired_null_restart_bias_width_pct": max_restart_bias,
        "report_samples": report_rows(full_rows),
        "all_step_samples": full_rows,
        "command_history": history,
    }


def main() -> int:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not EXE.exists():
        raise FileNotFoundError(EXE)

    configure_base()
    remove(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    pta.install_operator()
    nfc.install_current_redistribution_operator()
    pta.build()

    # Uninterrupted source=0 is diagnostic only. It is never an acceptance baseline.
    uninterrupted = paired.run_uninterrupted_null()

    common_control_history: list[dict] = []
    common_null_history: list[dict] = []

    # Shared prefix 0.00->0.05: actuator off.
    c0, crows0, cs0, cm0 = run_segment(
        "common_control_00", None, CURRENT_SOURCE, 0.0, 0.00, FIRST_START
    )
    n0, nrows0, ns0, nm0 = run_segment(
        "common_null_00", None, 0, 0.0, 0.00, FIRST_START
    )
    append_history(
        common_control_history, role="control", name="common_control_00",
        start=0.00, stop=FIRST_START, source=CURRENT_SOURCE, amp=0.0,
        directory=c0, status=cs0, manifest=cm0,
    )
    append_history(
        common_null_history, role="null", name="common_null_00",
        start=0.00, stop=FIRST_START, source=0, amp=0.0,
        directory=n0, status=ns0, manifest=nm0,
    )

    # Shared first pulse 0.05->0.15.
    c1, crows1, cs1, cm1 = run_segment(
        "common_control_01", c0, CURRENT_SOURCE, FIRST_AMP, FIRST_START, FIRST_STOP
    )
    n1, nrows1, ns1, nm1 = run_segment(
        "common_null_01", n0, 0, 0.0, FIRST_START, FIRST_STOP
    )
    append_history(
        common_control_history, role="control", name="common_control_01",
        start=FIRST_START, stop=FIRST_STOP, source=CURRENT_SOURCE, amp=FIRST_AMP,
        directory=c1, status=cs1, manifest=cm1,
    )
    append_history(
        common_null_history, role="null", name="common_null_01",
        start=FIRST_START, stop=FIRST_STOP, source=0, amp=0.0,
        directory=n1, status=ns1, manifest=nm1,
    )

    common_control_rows = crows0 + crows1
    common_null_rows = nrows0 + nrows1

    summaries: list[dict] = []
    flat_rows: list[dict] = []

    # Branch at each candidate second-pulse start. The null suffix is reused
    # across amplitudes because its source, state, and restart boundaries are
    # identical for all three amplitude branches.
    for second_start in SECOND_STARTS:
        start_tag = f"{second_start:.2f}".replace(".", "p")
        branch_control_history = list(common_control_history)
        branch_null_history = list(common_null_history)

        cb, cbrows, cbs, cbm = run_segment(
            f"s{start_tag}_control_gap",
            c1,
            CURRENT_SOURCE,
            0.0,
            FIRST_STOP,
            second_start,
        )
        nb, nbrows, nbs, nbm = run_segment(
            f"s{start_tag}_null_gap",
            n1,
            0,
            0.0,
            FIRST_STOP,
            second_start,
        )
        append_history(
            branch_control_history, role="control", name=f"s{start_tag}_control_gap",
            start=FIRST_STOP, stop=second_start, source=CURRENT_SOURCE, amp=0.0,
            directory=cb, status=cbs, manifest=cbm,
        )
        append_history(
            branch_null_history, role="null", name=f"s{start_tag}_null_gap",
            start=FIRST_STOP, stop=second_start, source=0, amp=0.0,
            directory=nb, status=nbs, manifest=nbm,
        )

        nf, nfrows, nfs, nfm = run_segment(
            f"s{start_tag}_null_final",
            nb,
            0,
            0.0,
            second_start,
            SECOND_STOP,
        )
        null_history = list(branch_null_history)
        append_history(
            null_history, role="null", name=f"s{start_tag}_null_final",
            start=second_start, stop=SECOND_STOP, source=0, amp=0.0,
            directory=nf, status=nfs, manifest=nfm,
        )
        null_rows = common_null_rows + nbrows + nfrows

        for second_amp in SECOND_AMPS:
            amp_tag = f"{abs(second_amp):.3f}".replace(".", "p")
            label = f"multi02_s{start_tag}_a{amp_tag}"

            cf, cfrows, cfs, cfm = run_segment(
                f"{label}_control_final",
                cb,
                CURRENT_SOURCE,
                second_amp,
                second_start,
                SECOND_STOP,
            )
            control_history = list(branch_control_history)
            append_history(
                control_history, role="control", name=f"{label}_control_final",
                start=second_start, stop=SECOND_STOP, source=CURRENT_SOURCE,
                amp=second_amp, directory=cf, status=cfs, manifest=cfm,
            )

            control_rows = common_control_rows + cbrows + cfrows
            full = eval_rows(control_rows, null_rows, uninterrupted)
            summary = summarize_case(
                label, second_start, second_amp, full,
                control_history + null_history,
            )
            summaries.append(summary)
            flat_rows.extend(
                {
                    "case": label,
                    "second_start": second_start,
                    "second_amp": second_amp,
                    **row,
                }
                for row in full
            )

    ranked = sorted(
        summaries,
        key=lambda s: (
            bool(s["sustained_safe_authority"]),
            float(s["positive_width_margin_pct"]),
            float(s["Jpk_guard_margin_pct"]),
            float(s["final_width_gain_pct"]),
            float(s["peak_width_gain_pct"]),
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    passes = [s for s in ranked if s["sustained_safe_authority"]]
    any_safe_point = any(s["width_gate_pass_any"] for s in summaries)
    any_final_safe = any(
        s["final_width_gate_pass"] and s["final_current_gate_pass"]
        for s in summaries
    )

    if passes:
        classification = (
            "M3DC1_TCT_PAIRED_RESTART_REFINED_SUSTAINED_SAFE_AUTHORITY"
        )
    elif any_final_safe or any_safe_point:
        classification = (
            "M3DC1_TCT_PAIRED_RESTART_REFINEMENT_TRANSIENT_SAFE_AUTHORITY"
        )
    else:
        classification = (
            "M3DC1_TCT_PAIRED_RESTART_REFINEMENT_NO_SAFE_AUTHORITY_FOUND"
        )

    report = {
        "classification": classification,
        "claim_boundary": (
            "Normalized native M3D-C1 paired-restart differential refinement only. "
            "The first pulse and frozen +0.020% width / +0.10% Jpk gates are "
            "unchanged. Acceptance is evaluated at every dt=0.01 sample from "
            "t=0.10 through t=0.30 against an identically restarted source=0 twin. "
            "No reactor-scale or experimental stabilization claim is implied."
        ),
        "audit": {
            "type": "paired_restart_multi_02_sustained_refinement",
            "dt": DT,
            "horizon": HORIZON,
            "evaluation_times": list(FULL_EVAL_TIMES),
            "report_times": list(REPORT_TIMES),
            "current_source": CURRENT_SOURCE,
            "profile_width": PROFILE_WIDTH,
            "first_pulse": {
                "start": FIRST_START,
                "stop": FIRST_STOP,
                "amp": FIRST_AMP,
            },
            "second_pulse": {
                "starts": list(SECOND_STARTS),
                "amps": list(SECOND_AMPS),
                "stop": SECOND_STOP,
            },
            "frozen_acceptance": {
                "continuous_width_gain_pct_gt": 0.0,
                "Jpk_change_pct_le_every_step": JPK_GATE_PCT,
                "width_gain_pct_gt_at_least_once": WIDTH_GATE_PCT,
                "final_width_gain_pct_gt": WIDTH_GATE_PCT,
            },
            "comparison": (
                "controlled restarted branch minus source=0 branch with identical "
                "restart boundaries"
            ),
            "branch_reuse": (
                "common 0.00->0.15 prefixes are reused; one source=0 suffix per "
                "second-start is reused across the three second-pulse amplitudes"
            ),
        },
        "sustained_pass_count": len(passes),
        "sustained_pass_cases": [s["case"] for s in passes],
        "best_case": best,
        "case_summaries": ranked,
    }

    pta.write_csv(OUT / "refinement_all_step_samples.csv", flat_rows)
    pta.write_csv(
        OUT / "refinement_case_summary.csv",
        [
            {
                "case": s["case"],
                "second_start": s["second_start"],
                "second_amp": s["second_amp"],
                "sustained_safe_authority": s["sustained_safe_authority"],
                "continuous_positive_width_t0p10_to_t0p30": (
                    s["continuous_positive_width_t0p10_to_t0p30"]
                ),
                "current_gate_pass_every_step_t0p10_to_t0p30": (
                    s["current_gate_pass_every_step_t0p10_to_t0p30"]
                ),
                "width_gate_pass_any": s["width_gate_pass_any"],
                "final_width_gate_pass": s["final_width_gate_pass"],
                "minimum_width_gain_pct": s["minimum_width_gain_pct"],
                "minimum_width_time": s["minimum_width_time"],
                "peak_width_gain_pct": s["peak_width_gain_pct"],
                "peak_width_time": s["peak_width_time"],
                "worst_Jpk_change_pct": s["worst_Jpk_change_pct"],
                "worst_Jpk_time": s["worst_Jpk_time"],
                "Jpk_guard_margin_pct": s["Jpk_guard_margin_pct"],
                "final_width_gain_pct": s["final_width_gain_pct"],
                "final_Jpk_change_pct": s["final_Jpk_change_pct"],
                "max_high_J_change_pct": s["max_high_J_change_pct"],
                "max_high_J_time": s["max_high_J_time"],
                "max_abs_paired_null_restart_bias_width_pct": (
                    s["max_abs_paired_null_restart_bias_width_pct"]
                ),
            }
            for s in ranked
        ],
    )
    write_json(OUT / "refinement_summary.json", report)
    (OUT / "runtime_provenance.txt").write_text(
        f"repo={REPO}\n"
        f"source={SRC}\n"
        f"baseline={BASE}\n"
        f"executable={EXE}\n"
        f"executable_sha256={pta.sha256_file(EXE)}\n"
        f"run_root={RUN_ROOT}\n"
        f"dt={DT}\n"
        f"horizon={HORIZON}\n"
        f"profile_width={PROFILE_WIDTH}\n"
        f"first_pulse={FIRST_START}->{FIRST_STOP}@{FIRST_AMP}\n"
        f"second_starts={list(SECOND_STARTS)}\n"
        f"second_amps={list(SECOND_AMPS)}\n"
        f"second_stop={SECOND_STOP}\n"
        f"width_gate_pct={WIDTH_GATE_PCT}\n"
        f"jpk_gate_pct={JPK_GATE_PCT}\n"
        "acceptance=every native step from 0.10 through 0.30\n"
        "comparison=paired restarted control minus identically restarted source0\n"
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
