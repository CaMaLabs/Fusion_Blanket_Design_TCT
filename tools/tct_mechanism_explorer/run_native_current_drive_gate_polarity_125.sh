#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
python3 - <<'PY'
"""Bounded native M3D-C1 current-drive gate and polarity delivery diagnostic.
Do not infer TCT stabilization from this two-step source-response isolation.
"""
import datetime
import hashlib
import json
import math
import pathlib
import sys

repo = pathlib.Path("/home/ubuntu/work/openmc/sweep")
sys.path.insert(0, str(repo / "tools/tct_mechanism_explorer"))
import native_feedback_controller_audit as native
import pulse_train_audit as pta

parent = "20261029-124-native-feedback-polarity-counterfactual"
out = repo / "validation_runs/m3dc1_tct_native_gate_polarity_125"
native.OUT = out
native.RUN_ROOT = pathlib.Path("/tmp/m3dc1_tct_native_gate_polarity_125_runs")
out.mkdir(parents=True, exist_ok=True)
metrics = ("W_sheet", "Jpk", "Jint_high", "Reconnected_Flux",
           "magnetic_energy", "center_abs_current", "shoulder_abs_current")
report = {
    "schema_version": 1,
    "parent_result_job_id": parent,
    "fuel_track": "fuel_agnostic_control",
    "machine": "normalized-native-M3D-C1",
    "shot_ids": [],
    "classification": "M3DC1_NATIVE_CURRENT_DRIVE_GATE_RESPONSE_UNRESOLVED",
    "claim_boundary": "Native normalized M3D-C1 source delivery diagnostic only; not an experimental shot handoff, causal TCT stabilization, dimensional lithium result, p-B11 or reactor-net-power claim.",
    "frozen_gates_preserved": {"width_gain_pct_gt": 0.02, "Jpk_change_pct_le": 0.10},
    "zero_equivalence_tolerance": 1e-12,
    "gate_windows": {"edge": [0.0, 0.02], "extended": [0.0, 0.03]},
    "dt": 0.01, "steps": 2, "source_mode": 4,
    "command_amplitudes": [-0.005, 0.0, 0.005],
    "source_gate_changes_only": True,
    "physics_equations_unchanged": True,
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
try:
    if abs(native.DT - 0.01) > 1e-12:
        raise RuntimeError("DT_PREREQUISITE_CHANGED")
    pta.install_operator()
    native.install_current_redistribution_operator()
    pta.build()
    report["executable_sha256"] = pta.sha256_file(native.EXE)
    configs = (
        ("baseline", 0, 0.0, 0.03),
        ("same_mode_zero", 4, 0.0, 0.03),
        ("edge_negative", 4, -0.005, 0.02),
        ("edge_positive", 4, 0.005, 0.02),
        ("extended_negative", 4, -0.005, 0.03),
        ("extended_positive", 4, 0.005, 0.03),
    )
    runs = {}
    for name, source, amp, off in configs:
        d = native.write_input(name, source, amp, 0, 0.0, off, nmax_steps=2)
        print("[gate-polarity] running " + name, flush=True)
        native.execute(d)
        rows = native.safe_extract(d)
        if len(rows) < 2:
            raise RuntimeError(name + " insufficient output frames")
        runs[name] = rows
    base = runs["baseline"]
    def compare(a, b):
        aa, bb = runs[a], runs[b]
        if len(aa) != len(bb):
            raise RuntimeError("FRAME_COUNT_MISMATCH: " + a + " / " + b)
        max_abs = {k: 0.0 for k in metrics}
        max_relative = {k: 0.0 for k in metrics}
        for ra, rb in zip(aa, bb):
            if abs(ra["time"] - rb["time"]) > 1e-8:
                raise RuntimeError("TIME_GRID_MISMATCH: " + a + " / " + b)
            for k in metrics:
                va, vb = float(ra[k]), float(rb[k])
                if not (math.isfinite(va) and math.isfinite(vb)):
                    raise RuntimeError("NONFINITE_OBSERVABLE: " + k)
                delta = abs(va - vb)
                max_abs[k] = max(max_abs[k], delta)
                max_relative[k] = max(max_relative[k], delta / max(abs(vb), 1e-12))
        return {"max_abs": max_abs, "max_relative": max_relative}
    report["comparisons"] = {
        "zero_vs_baseline": compare("same_mode_zero", "baseline"),
        "edge_positive_vs_zero": compare("edge_positive", "same_mode_zero"),
        "edge_negative_vs_zero": compare("edge_negative", "same_mode_zero"),
        "extended_positive_vs_zero": compare("extended_positive", "same_mode_zero"),
        "extended_negative_vs_zero": compare("extended_negative", "same_mode_zero"),
        "edge_polarity_difference": compare("edge_positive", "edge_negative"),
        "extended_polarity_difference": compare("extended_positive", "extended_negative"),
        "positive_gate_window_difference": compare("extended_positive", "edge_positive"),
        "negative_gate_window_difference": compare("extended_negative", "edge_negative"),
    }
    zero = report["comparisons"]["zero_vs_baseline"]["max_abs"]
    report["zero_equivalence"] = {
        "pass": all(zero[k] <= 1e-12 for k in
                    ("W_sheet", "Jpk", "Jint_high", "Reconnected_Flux", "magnetic_energy")),
        "max_abs_metric_delta": max(zero.values()),
    }
    report["run_frames"] = {name: len(rows) for name, rows in runs.items()}
    report["source_response_observed"] = any(
        report["comparisons"][name]["max_abs"][k] > 1e-12
        for name in ("edge_polarity_difference", "extended_polarity_difference")
        for k in metrics
    )
    if not report["zero_equivalence"]["pass"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_ZERO_EQUIVALENCE_FAILED"
    elif report["source_response_observed"]:
        report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_GATE_RESPONSE_DIAGNOSTIC_COMPLETE"
    report["interpretation"] = (
        "Two-step matched source-mode polarity/gate diagnostic only. Nonzero observable "
        "differences indicate a response, not proof of delivered current-drive forcing, "
        "control authority, native handoff equivalence, or frozen-gate stabilization."
    )
except Exception as exc:
    report["pipeline_error"] = type(exc).__name__ + ": " + str(exc)
    report["classification"] = "M3DC1_NATIVE_CURRENT_DRIVE_GATE_DIAGNOSTIC_PIPELINE_BLOCKED"
tmp = out / "native_gate_summary.json.tmp"
tmp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
tmp.replace(out / "native_gate_summary.json")
print(json.dumps(report, indent=2, sort_keys=True))
PY
