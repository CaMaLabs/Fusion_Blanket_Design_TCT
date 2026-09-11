#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import native_amplitude_handoff_refinement_audit as base

REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_preemptive_handoff_refinement"
RUN_ROOT = Path("/tmp/m3dc1_tct_native_preemptive_handoff_refinement_runs")

HANDOFF_TIMES = (0.09, 0.10, 0.11)
CONTINUATION_AMPS = (0.0, -0.010, -0.015, -0.020, -0.025)
STRONG_START = 0.05
STRONG_AMP = -0.030
HORIZON = 0.30

_original_summarize = base.summarize_handoff


def summarize_preemptive(label, handoff, continuation_amp, rows, baseline_rows):
    s = _original_summarize(
        label=label,
        handoff=handoff,
        continuation_amp=continuation_amp,
        rows=rows,
        baseline_rows=baseline_rows,
    )
    s["kind"] = "uninterrupted_native_preemptive_handoff_refinement"
    s["first_start"] = STRONG_START
    s["first_stop"] = handoff
    s["first_amp"] = STRONG_AMP
    s["second_start"] = handoff
    s["second_stop"] = HORIZON
    s["second_amp"] = continuation_amp
    s["handoff_time"] = handoff
    s["strong_amp"] = STRONG_AMP
    s["continuation_amp"] = continuation_amp
    return s


def remap_classification(classification):
    mapping = {
        "M3DC1_TCT_NATIVE_HANDOFF_ZERO_EQUIVALENCE_FAILED":
            "M3DC1_TCT_NATIVE_PREEMPTIVE_HANDOFF_ZERO_EQUIVALENCE_FAILED",
        "M3DC1_TCT_NATIVE_HANDOFF_SUSTAINED_SAFE_AUTHORITY":
            "M3DC1_TCT_NATIVE_PREEMPTIVE_HANDOFF_SUSTAINED_SAFE_AUTHORITY",
        "M3DC1_TCT_NATIVE_HANDOFF_TRANSIENT_SAFE_AUTHORITY":
            "M3DC1_TCT_NATIVE_PREEMPTIVE_HANDOFF_TRANSIENT_SAFE_AUTHORITY",
        "M3DC1_TCT_NATIVE_HANDOFF_NO_SAFE_AUTHORITY_FOUND":
            "M3DC1_TCT_NATIVE_PREEMPTIVE_HANDOFF_NO_SAFE_AUTHORITY_FOUND",
    }
    if classification not in mapping:
        raise RuntimeError(f"unexpected base classification: {classification}")
    return mapping[classification]


def main():
    base.OUT = OUT
    base.RUN_ROOT = RUN_ROOT
    base.HANDOFF_TIMES = HANDOFF_TIMES
    base.CONTINUATION_AMPS = CONTINUATION_AMPS
    base.STRONG_START = STRONG_START
    base.STRONG_AMP = STRONG_AMP
    base.HORIZON = HORIZON
    base.summarize_handoff = summarize_preemptive

    # Do not redirect stdout here. base.main() emits one progress line per native
    # M3D-C1 case; streaming those lines is important because a full sweep can
    # otherwise look hung for many minutes even while the solver is healthy.
    rc = base.main()

    summary_path = OUT / "native_handoff_refinement_summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"base audit did not produce {summary_path}")

    report = json.loads(summary_path.read_text())
    report["classification"] = remap_classification(report["classification"])
    report["claim_boundary"] = (
        "Normalized native M3D-C1 uninterrupted preemptive amplitude-handoff "
        "audit only. The source=4 spatial profile and frozen +0.020% width / "
        "+0.10% Jpk gates are unchanged. No restart is used for actuator "
        "switching. Acceptance is evaluated at every dt=0.01 sample from "
        "t=0.10 through t=0.30. No reactor-scale or experimental stabilization "
        "claim is implied."
    )
    report["audit"]["type"] = "uninterrupted_native_preemptive_handoff_refinement"
    report["audit"]["reason"] = (
        "the t=0.12/0.13/0.14 handoff sweep suppressed the independent high-J "
        "spike when continued negative drive was retained, but Jpk still "
        "violated the frozen guard at t=0.14; this audit moves the handoff to "
        "t=0.09/0.10/0.11 to test response latency/memory"
    )
    report["audit"]["strong_start"] = STRONG_START
    report["audit"]["strong_amp"] = STRONG_AMP
    report["audit"]["handoff_times"] = list(HANDOFF_TIMES)
    report["audit"]["continuation_amps"] = list(CONTINUATION_AMPS)
    report["audit"]["restart_used_for_switching"] = False

    base.write_json(summary_path, report)

    provenance = OUT / "runtime_provenance.txt"
    with provenance.open("a") as f:
        f.write("audit_phase=preemptive_handoff_latency_test\n")
        f.write(f"preemptive_handoff_times={list(HANDOFF_TIMES)}\n")
        f.write(f"preemptive_continuation_amps={list(CONTINUATION_AMPS)}\n")
        f.write("metadata_first_stop=actual handoff time per case\n")

    print("\n===== PREEMPTIVE HANDOFF CLASSIFICATION =====", flush=True)
    print(report["classification"], flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
