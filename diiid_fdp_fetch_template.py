#!/usr/bin/env python3
"""Authorized-user template for replacing reconstructed DIII-D diagnostic traces."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


SHOT = 158103
WINDOW_MS = (3756.325, 3806.325)
OUTPUT = Path("diiid_158103_authorized_diagnostics.csv")


def main() -> int:
    try:
        from toksearch_d3d import ImasSignal, PtDataSignal
    except ImportError as error:
        raise SystemExit(
            "Install the official GA-FDP/toksearch_d3d environment and configure "
            "~/.fdp/token or BEARER_TOKEN before running this authorized-user template."
        ) from error

    signals = {
        "ip_a": PtDataSignal("ip").fetch(SHOT),
        "density": PtDataSignal("dssdenest").fetch(SHOT),
    }
    ece = ImasSignal("ece.channel.t_e.data").fetch(SHOT)
    np.savez_compressed(
        "diiid_158103_authorized_ece.npz",
        data=np.asarray(ece["data"]),
        times=np.asarray(ece.get("times", [])),
    )
    # Magnetic precursor, event marker, and actuator channels are deliberately
    # left for an authorized DIII-D reviewer to select for this shot.
    manifest = {
        "shot": SHOT,
        "window_ms": WINDOW_MS,
        "fetched": sorted(signals) + ["edge_ece_te"],
        "reviewer_required": [
            "select_edge_ece_channels",
            "magnetic_precursor",
            "event_marker",
            "actuator_command_response",
        ],
    }
    Path("diiid_158103_authorized_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["signal", "time_ms", "value"])
        for name, result in signals.items():
            times = result.get("times", [])
            data = result["data"]
            for time, value in zip(times, data):
                if WINDOW_MS[0] <= float(time) <= WINDOW_MS[1]:
                    writer.writerow([name, float(time), float(value)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
