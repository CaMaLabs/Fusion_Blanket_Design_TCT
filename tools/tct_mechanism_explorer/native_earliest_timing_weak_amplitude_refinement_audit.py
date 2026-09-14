#!/usr/bin/env python3
"""Narrow continuation of the native timing/amplitude frontier.

Job 004 showed that moving the handoff earlier improved both the Jpk excursion
and peak width at fixed post-handoff amplitude. This wrapper reuses the fully
validated uninterrupted two-profile audit while restricting the search to the
earliest feasible native handoffs and slightly weaker post-handoff amplitudes.
The frozen +0.020% width and +0.10% Jpk gates are unchanged.
"""
from __future__ import annotations

from pathlib import Path

import native_preemptive_timing_amplitude_refinement_audit as audit


def main() -> int:
    audit.OUT = Path("/home/ubuntu/work/openmc/sweep/validation_runs/m3dc1_tct_native_earliest_timing_weak_amplitude_refinement")
    audit.RUN_ROOT = Path("/tmp/m3dc1_tct_native_earliest_timing_weak_amplitude_refinement_runs")
    audit.HANDOFFS = (0.05, 0.06, 0.07)
    audit.SECOND_AMPLITUDES = (-0.0148, -0.0150, -0.0152)
    return audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
