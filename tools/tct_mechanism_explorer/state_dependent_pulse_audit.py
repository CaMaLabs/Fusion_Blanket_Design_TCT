#!/usr/bin/env python3
"""Audit dead-time/re-arm policies for the native magnetic impulse.

This is a deterministic state-dependent *proxy*: it uses measured impulse timing
to choose re-arm intervals, but M3D-C1 is still run in batch mode with a
predeclared schedule. It must not be described as closed-loop feedback.
"""
from __future__ import annotations

import json
from pathlib import Path

import pulse_train_audit as pta

REPO = pta.REPO
OUT = REPO / "validation_runs/m3dc1_tct_state_dependent_pulse"
RUN_ROOT = Path("/tmp/m3dc1_tct_state_dependent_pulse_runs")

# Re-arm intervals are intentionally longer than the 0.05-unit pulse width.
# These are schedule proxies for: fire -> observe/recover -> re-arm.
CASES = [
    {"name": "single_reference", "period": 0.0, "pulse_width": 0.0, "t_off": 0.05},
    {"name": "rearm_p150_w050", "period": 0.15, "pulse_width": 0.05, "t_off": 0.35},
    {"name": "rearm_p200_w050", "period": 0.20, "pulse_width": 0.05, "t_off": 0.35},
    {"name": "rearm_p250_w050", "period": 0.25, "pulse_width": 0.05, "t_off": 0.35},
    {"name": "rearm_p150_w020", "period": 0.15, "pulse_width": 0.02, "t_off": 0.35},
]


def main() -> None:
    pta.OUT = OUT
    pta.RUN_ROOT = RUN_ROOT
    pta.CASES = CASES
    pta.run_all()

    matrix_path = OUT / "pulse_train_matrix.csv"
    (OUT / "controller_policy.json").write_text(
        json.dumps(
            {
                "controller_type": "deterministic_dead_time_rearm_proxy",
                "closed_loop": False,
                "actuator": "native_normalized_m3dc1_magnetic_operator",
                "amplitude": pta.AMP,
                "pulse_widths": sorted({c["pulse_width"] for c in CASES}),
                "rearm_periods": sorted({c["period"] for c in CASES if c["period"] > 0}),
                "trigger_proxy": "predeclared re-arm period; no live state readback",
                "feedback_required_for_claim": True,
                "source_matrix": str(matrix_path),
                "claim_boundary": (
                    "This audit tests dead-time/re-arm schedules. It does not "
                    "demonstrate a closed-loop controller or lithium dimensional transfer."
                ),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
