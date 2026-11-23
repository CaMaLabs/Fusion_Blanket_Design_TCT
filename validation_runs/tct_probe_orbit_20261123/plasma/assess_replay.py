"""Apply the archived sheet width and peak-current acceptance thresholds."""

import argparse
import json
from pathlib import Path

import numpy as np

from analyze import PEAK, WIDTH, delta, margin, paired_width
from measure import STATIONS
from run import CADENCE, END
from steered_replay import CASE_CONFIGS, REPLAY_LEVELS, ROOT


def read(level, role, case):
    path = ROOT / "runs" / f"{level}_{role}_{case}.json"
    data = json.loads(path.read_text())
    shape, step = REPLAY_LEVELS[level]
    assert data["case"] == role and data["mesh"] == list(shape) and data["dt"] == step
    assert np.array_equal(data["stations"], STATIONS)
    assert len(data["records"]) == round(END / CADENCE) + 1
    return data


def assess(levels, case):
    pairs_by_level = [(read(level, case, case), read(level, "baseline", case)) for level in levels]
    false_width = max(treatment["diagnostic_benchmark"]["max_false_width_gain_pct"]
                      for treatment, _ in pairs_by_level)
    for treatment, baseline in pairs_by_level:
        assert treatment["geometry"] == baseline["geometry"]

    records = []
    for i in range(round(END / CADENCE) + 1):
        pairs = [[treatment["records"][i], baseline["records"][i]]
                 for treatment, baseline in pairs_by_level]
        first = pairs[0][0]
        for treatment, baseline in pairs:
            assert treatment["t"] == baseline["t"] == first["t"]
            for key in ("center", "velocity", "valid_peak_points"):
                assert treatment[key] == baseline[key] == first[key], (i, key)
        widths, n_width = paired_width(pairs, "width")
        integral, n_integral = paired_width(pairs, "integral_width")
        peaks = [float(delta(a["annulus_peak_j"], b["annulus_peak_j"])) for a, b in pairs]
        width_error = None
        peak_error = None
        if len(levels) == 3:
            width_error = None if not n_width else margin([row["mean"] for row in widths]) + false_width
            peak_error = margin(peaks)
        width_gain = widths[-1]["mean"]
        adjusted_width = None if width_gain is None else width_gain - (width_error or false_width)
        adjusted_peak = peaks[-1] + (peak_error or 0.)
        complete = (n_width == len(STATIONS) and adjusted_width is not None
                    and adjusted_width > WIDTH and adjusted_peak <= PEAK)
        records.append(dict(
            t=first["t"], widths=widths, integral_widths=integral, peak_changes_pct=peaks,
            common_width_stations=n_width, common_integral_stations=n_integral,
            width_margin_pp=width_error, peak_margin_pp=peak_error, adjusted_width_pct=adjusted_width,
            adjusted_peak_pct=adjusted_peak, passes_gate=complete,
            raw_full_coverage_gate=(n_width == len(STATIONS) and width_gain is not None
                                    and width_gain > WIDTH and peaks[-1] <= PEAK),
            partial_coverage_gate=(n_width >= 27 and adjusted_width is not None
                                   and adjusted_width > WIDTH and adjusted_peak <= PEAK),
        ))
    return dict(geometry=pairs_by_level[0][0]["geometry"], frames=records)


def verify_legacy(archive):
    current = read("archive_mesh", "hold", "hold")
    reference = json.loads((archive / "archive_mesh_hold.json").read_text())
    for left, right in zip(current["records"], reference["records"], strict=True):
        assert left["t"] == right["t"]
        assert left["center"] == right["center"]
        assert left["velocity"] == [0., right["velocity"], 0.]
        assert left["profiles"] == right["profiles"]
        assert left["annulus_peak_j"] == right["annulus_peak_j"]
    return len(current["records"])


def summarize(case, result):
    frames = result["frames"]
    valid = [row for row in frames if row["common_width_stations"] == len(STATIONS)]
    best_width = max(valid, key=lambda row: row["widths"][-1]["mean"], default=None)
    safe = [row for row in valid if row["adjusted_peak_pct"] <= PEAK]
    best_safe = max(safe, key=lambda row: row["adjusted_width_pct"], default=None)
    widest_any = max((row for row in frames if row["common_width_stations"] >= 27),
                     key=lambda row: row["widths"][-1]["mean"], default=None)
    passes = [round(row["t"], 4) for row in frames if row["passes_gate"]]
    print(case, "full passes", passes, "partial passes", sum(row["partial_coverage_gate"] for row in frames),
          "raw passes", sum(row["raw_full_coverage_gate"] for row in frames),
          "full coverage", len(valid), flush=True)
    for label, row in (("largest full width", best_width), ("best under peak cap", best_safe),
                       ("largest width at 27+ stations", widest_any)):
        if row is not None:
            print(" ", label, f"t={row['t']:.4f}", row["common_width_stations"],
                  f"width={row['widths'][-1]['mean']:+.5f}%",
                  f"peak={row['peak_changes_pct'][-1]:+.5f}%",
                  f"adjusted_width={row['adjusted_width_pct']:+.5f}%",
                  f"adjusted_peak={row['adjusted_peak_pct']:+.5f}%", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coarse", action="store_true")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    legacy_frames = verify_legacy(args.archive) if args.archive else None
    levels = ("archive_mesh",) if args.coarse else ("archive_mesh", "fine_half_step", "fine_quarter_step")
    cases = {case: assess(levels, case) for case in CASE_CONFIGS}
    receipt = dict(levels=levels, legacy_frames_reproduced=legacy_frames, cases=cases,
                   width_pct_gate_exclusive=WIDTH, peak_current_pct_gate_inclusive=PEAK)
    suffix = "_coarse" if args.coarse else ""
    (ROOT / "runs" / f"replay_summary{suffix}.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    for name, result in cases.items():
        summarize(name, result)
    print("Archived hold frames reproduced:", legacy_frames, flush=True)


if __name__ == "__main__":
    main()
