"""Integrate the published JET outer-target power trace in physical units."""

import argparse
import hashlib
import json
from pathlib import Path

import fitz
import numpy as np
from scipy.integrate import cumulative_trapezoid


SOURCE = "https://pure.mpg.de/rest/items/item_2143150/component/file_2143149/content"
PDF_SHA256 = "815eff8cd405ca64779cab9bb80aa4c87939e5c2b4737b3309f6e65b53116f96"
PAGE = 23
NOMINAL_WINDOW_S = (-.0009, .0021)
SENSITIVITY_WINDOWS_S = ((-.001, .002), (-.001, .0025), (-.0008, .002), (-.0008, .0025))


def plot_points(drawing):
    segments = drawing["items"]
    if any(kind != "l" for kind, *_ in segments):
        raise ValueError("Expected a vector polyline in the reference figure")
    return np.array([tuple(segments[0][1]), *(tuple(segment[2]) for segment in segments)])


def extract_figure(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError("Unrecognized revision of the source PDF")
    with fitz.open(path) as doc:
        page = doc[PAGE - 1]
        if "4.2.2-2." not in page.get_text():
            raise ValueError("Reference figure is absent from its expected page")
        paths = page.get_drawings()
    # Convert PDF coordinates using the -3000 to +3000 us x-axis, the
    # 50 MW tick on the power axis and the 0 to 120 kJ energy axis.
    frame = paths[4]["rect"]
    zero_x = (frame.x0 + frame.x1) / 2
    s_per_point = .006 / frame.width
    w_per_point = 50e6 / (frame.y1 - plot_points(paths[12])[0, 1])
    j_per_point = 120e3 / frame.height

    def scaled_path(index, y_scale):
        xy = plot_points(paths[index])
        return (xy[:, 0] - zero_x)*s_per_point, (frame.y1 - xy[:, 1])*y_scale

    # The blue trace is IR-derived target power. The red trace is cumulative
    # energy. The lower and upper black guides mark the background trends.
    time_s, power_w = scaled_path(40, w_per_point)
    energy_time_s, energy_j = scaled_path(1, j_per_point)
    before = scaled_path(33, j_per_point)
    after = scaled_path(45, j_per_point)
    if (len(time_s) != 81 or not np.all(np.diff(time_s) > 0.)
            or not np.array_equal(time_s, energy_time_s)):
        raise ValueError("Unexpected power and energy trace layout")
    pre_slope, pre_intercept = np.polyfit(*before, deg=1)
    post_slope, post_intercept = np.polyfit(*after, deg=1)
    if not np.isclose(pre_slope, post_slope, rtol=.001):
        raise ValueError("The pre- and post-ELM background guides diverge")
    return time_s, power_w, energy_j, float(pre_slope), float(post_intercept-pre_intercept)


def estimate_window(time_s, net_power_w, cumulative_j, baseline_w, bounds):
    start, stop = bounds
    knots = np.r_[start, time_s[(start < time_s) & (time_s < stop)], stop]
    power = np.interp(knots, time_s, net_power_w)
    integrated_j = float(cumulative_trapezoid(power, knots)[-1])
    ends = np.interp(bounds, time_s, cumulative_j)
    from_curve_j = float(ends[1] - ends[0] - baseline_w*(stop-start))
    positive_j = cumulative_trapezoid(np.maximum(power, 0.), knots, initial=0.)
    t10, t50, t90 = np.interp(positive_j[-1] * np.array([.10, .50, .90]), positive_j, knots)
    peak_i = int(np.argmax(power))
    return dict(window_s=bounds, deposited_energy_j=integrated_j, from_energy_curve_j=from_curve_j,
                peak_excess_power_w=float(power[peak_i]), peak_time_s=float(knots[peak_i]),
                t10_s=float(t10), t50_s=float(t50), t90_s=float(t90),
                t10_to_t90_s=float(t90-t10))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    time, power, energy, baseline, trend_step = extract_figure(args.source_pdf)
    windows = [estimate_window(time, power-baseline, energy, baseline, bounds)
               for bounds in (NOMINAL_WINDOW_S, *SENSITIVITY_WINDOWS_S)]
    for row in windows:
        if abs(row["deposited_energy_j"] / row["from_energy_curve_j"] - 1.) >= .01:
            raise ArithmeticError("Integrated power disagrees with the published cumulative curve")
    result = dict(
        source=SOURCE, source_sha256=PDF_SHA256, source_page=PAGE, figure="4.2.2-2",
        experimental_source_doi="10.1016/S0022-3115(02)01477-0",
        scope="Published vector figure, one JET Type I ELM, outboard divertor target",
        time_origin="Published figure zero, approximately the target power maximum",
        baseline_power_w=baseline, published_energy_trend_step_j=trend_step,
        nominal=windows[0], window_sensitivity=windows[1:],
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
