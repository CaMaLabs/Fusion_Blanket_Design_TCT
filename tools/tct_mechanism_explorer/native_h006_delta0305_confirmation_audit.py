#!/usr/bin/env python3
"""Test one minimally stronger second-profile shoulder redistribution at the h=0.06 frontier.

Job 008 changed only second-profile shoulder_delta from 0.300 to 0.295 and moved
worst Jpk in the wrong direction while preserving the frozen width gate. This
audit therefore tests the opposite local direction, shoulder_delta=0.305,
holding timing, amplitudes, widths, horizon, sampling, solver physics, and the
frozen +0.020% width / +0.10% Jpk gates unchanged.

Claim boundary remains normalized native M3D-C1 only.
"""
from __future__ import annotations

from pathlib import Path

import native_preemptive_timing_amplitude_refinement_audit as audit


def main() -> int:
    audit.OUT = Path("/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_h006_delta0305_confirmation")
    audit.RUN_ROOT = Path("/tmp/m3dc1_tct_native_h006_delta0305_confirmation_runs")
    audit.HANDOFFS = (0.06,)
    audit.SECOND_AMPLITUDES = (-0.01520,)
    audit.SECOND_DELTA = 0.305
    return audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
