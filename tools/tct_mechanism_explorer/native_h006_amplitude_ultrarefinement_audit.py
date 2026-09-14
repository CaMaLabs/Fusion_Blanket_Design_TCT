#!/usr/bin/env python3
"""Ultra-refine the local native amplitude pocket at handoff t=0.06.

Job 006 found a non-monotone local Jpk minimum at second_amp=-0.01520:
peak width +0.0210247% passed the frozen +0.020% width gate while worst Jpk
+0.1018116% missed the frozen +0.10% current gate by 0.0018116 percentage
points. Neighboring points at -0.01515 and -0.01525 were materially worse in
Jpk, so this audit maps only the immediate +/-2e-5 neighborhood. Solver
physics, profiles, first-stage amplitude, horizon, sampling, and acceptance
gates are unchanged.
"""
from __future__ import annotations

from pathlib import Path

import native_preemptive_timing_amplitude_refinement_audit as audit


def main() -> int:
    audit.OUT = Path("/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_h006_amplitude_ultrarefinement")
    audit.RUN_ROOT = Path("/tmp/m3dc1_tct_native_h006_amplitude_ultrarefinement_runs")
    audit.HANDOFFS = (0.06,)
    audit.SECOND_AMPLITUDES = (-0.01518, -0.01519, -0.01520, -0.01521, -0.01522)
    return audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
