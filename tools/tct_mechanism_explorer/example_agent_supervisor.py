#!/usr/bin/env python3
"""Example stdin/stdout supervisor.

This intentionally uses no LLM. It demonstrates the protocol an OpenClaw/local
agent wrapper can implement.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    state = json.load(sys.stdin)
    stats = state.get("mechanism_stats", {})
    weights = {}
    notes = []

    for mechanism in state.get("allowed_mechanisms", []):
        row = stats.get(mechanism, {})
        count = max(int(row.get("count", 0)), 1)
        impulse = int(row.get("impulse_authority", 0))
        sustained = int(row.get("sustained", 0))
        if impulse and not sustained:
            weights[mechanism] = 1.5
            notes.append(f"{mechanism}: transient authority but sustained gate weak")
        elif sustained:
            weights[mechanism] = 2.5
            notes.append(f"{mechanism}: sustained response observed")
        elif count >= 4 and impulse == 0:
            weights[mechanism] = 0.5
        else:
            weights[mechanism] = 1.0

    json.dump({
        "mechanism_weights": weights,
        "proposals": [],
        "notes": "; ".join(notes) or "no strong family evidence yet",
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
