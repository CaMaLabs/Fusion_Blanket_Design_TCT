"""Recover detailed steered tracks for the local plasma replay."""

import argparse
import json
from pathlib import Path

import numpy as np

from fields import FieldMap, RADIUS, ROOT
from orbit import trajectory
from weight_shape import CONTROLLERS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    report = json.loads((ROOT / "runs/weight_shape_fine_compound_speed_scaled_drag_momentum.json").read_text())
    model = FieldMap(*report["field_grid"])
    metadata = {"radius_m": RADIUS, "field_grid": report["field_grid"], "cases": {}}
    files = {}
    for direction in (1, -1):
        case = min(
            (row for row in report["trajectories"]
             if row["direction"] == direction and row["load"] == "same_area"),
            key=lambda row: row["corridor_margin_m"],
        )
        name = "forward" if direction == 1 else "reverse"
        kwargs = dict(
            traces=True, balanced_height=case["reference_height_m"], direction=direction,
            drag_per_moment=case["drag_at_nominal_speed_T_m"], kick_at_lap_one_m_s=case["kick_m_s"],
            guide_weights=CONTROLLERS["momentum"], hold_angular_momentum=True,
        )
        args_for_run = (model, case["mode"], case["kappa_Am2_kg"], case["gravity"],
                        case["phase_deg"], case["launch"], case["cutoff_hz"])
        reproduced, _ = trajectory(*args_for_run, steps_per_lap=576, **kwargs)
        for key in ("laps", "elapsed_s", "radial_peak_m", "vertical_peak_m", "kick_time_s"):
            assert abs(reproduced[key] - case[key]) < 1e-10, (key, reproduced[key], case[key])
        refined, trace = trajectory(*args_for_run, steps_per_lap=2304, **kwargs)
        assert refined["outcome"] == "completed" and refined["kick_time_s"] is not None
        files[name] = trace
        field = model.field(RADIUS, case["reference_height_m"])
        metadata["cases"][name] = dict(archived_case=case, refined_case=refined,
                                       reference_field_R_phi_Z_T=field.tolist())
        print(name, f"phase {case['phase_deg']}°, {len(trace)} trace samples", flush=True)
    args.destination.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.destination / "orbit_tracks.npz", **files)
    (args.destination / "orbit_tracks.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
