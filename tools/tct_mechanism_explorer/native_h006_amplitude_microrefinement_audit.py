#!/usr/bin/env python3
"""Micro-refine the near-gate native timing/amplitude frontier at t=0.06.

Job 005 found that handoff t=0.06 with second_amp=-0.0152 retained the frozen
+0.020% width gate while missing the +0.10% Jpk gate by only 0.001812 percentage
points. This wrapper reuses the validated uninterrupted native timing/amplitude
audit, fixes the handoff at t=0.06, and probes a narrow amplitude band around
that near-miss. No solver physics or acceptance gates are changed.
"""
from __future__ import annotations

from pathlib import Path

import native_preemptive_timing_amplitude_refinement_audit as audit


def main() -> int:
    audit.OUT = Path("/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_h006_amplitude_microrefinement")
    audit.RUN_ROOT = Path("/tmp/m3dc1_tct_native_h006_amplitude_microrefinement_runs")
    audit.HANDOFFS = (0.06,)
    audit.SECOND_AMPLITUDES = (-0.01510, -0.01515, -0.01520, -0.01525, -0.01530)
    return audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
