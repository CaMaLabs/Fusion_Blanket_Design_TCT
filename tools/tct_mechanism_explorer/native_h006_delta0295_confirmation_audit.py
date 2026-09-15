#!/usr/bin/env python3
"""Test one minimally weaker second-profile shoulder redistribution at the h=0.06 frontier.

Job 007 confirmed that the exact second_amp=-0.01520 point retains the frozen
width gate but still misses the frozen Jpk gate by 0.0018116 percentage points.
The +/-1e-5 amplitude neighbors are worse, so further amplitude interpolation is
not justified. This audit changes only second-profile shoulder_delta from 0.300
to 0.295, holding timing, amplitudes, widths, horizon, sampling, solver physics,
and frozen gates unchanged. The hypothesis is that a 1.67% reduction in the
shoulder redistribution strength can buy the remaining Jpk margin while the
+0.0010247 percentage-point peak-width margin absorbs the small weakening.
"""
from __future__ import annotations

from pathlib import Path

import native_preemptive_timing_amplitude_refinement_audit as audit


def main() -> int:
    audit.OUT = Path("/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_h006_delta0295_confirmation")
    audit.RUN_ROOT = Path("/tmp/m3dc1_tct_native_h006_delta0295_confirmation_runs")
    audit.HANDOFFS = (0.06,)
    audit.SECOND_AMPLITUDES = (-0.01520,)
    audit.SECOND_DELTA = 0.295
    return audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
