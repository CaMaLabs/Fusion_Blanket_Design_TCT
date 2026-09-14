#!/usr/bin/env python3
"""Focused preemptive spatial-profile handoff audit.

Reuses the validated uninterrupted two-profile operator and its zero/same-profile
equivalence controls.  This follow-up moves the handoff earlier to test whether
the persistent t=0.14--0.16 excursion is dominated by actuator/profile response
latency rather than the tested second-profile geometry itself.
"""
from pathlib import Path

import native_two_profile_handoff_audit as base

REPO = Path("/home/ubuntu/work/openmc/sweep")
base.OUT = REPO / "validation_runs/m3dc1_tct_native_preemptive_two_profile_handoff"
base.RUN_ROOT = Path("/tmp/m3dc1_tct_native_preemptive_two_profile_handoff_runs")

# Keep the first profile, amplitude, horizon, frozen gates, and equivalence
# checks exactly as in the parent audit.  Only move the spatial handoff earlier.
base.HANDOFF_TIMES = (0.09, 0.10, 0.11)
base.SECOND_SHOULDER_WIDTHS = (0.40,)
base.SECOND_DELTAS = (0.30,)

if __name__ == "__main__":
    raise SystemExit(base.main())
