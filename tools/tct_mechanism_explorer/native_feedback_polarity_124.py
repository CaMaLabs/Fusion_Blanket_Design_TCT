#!/usr/bin/env python3
"""Native M3D-C1 polarity counterfactual of acknowledged Job 106.

Reuses the frozen native solver, initial state, source operator, segment cadence,
baseline, zero-equivalence and scientific gates. Only control command polarity
is reversed. Results are isolated from Job 106.
"""
from pathlib import Path
import native_feedback_controller_audit as native

native.OUT = native.REPO / "validation_runs/m3dc1_tct_native_feedback_polarity_124"
native.RUN_ROOT = Path("/tmp/m3dc1_tct_native_feedback_polarity_124_runs")
native.BIAS_AMP = +0.002
native.AGGRESSIVE_AMP = +0.02
native.HOLD_AMP = +0.005
native.ACTIVE_BRAKE_AMP = -0.005

if __name__ == "__main__":
    raise SystemExit(native.main())
