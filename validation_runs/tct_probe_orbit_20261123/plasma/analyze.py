"""Compare the core-effect trajectories across meshes and time steps."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from measure import STATIONS
from run import BRAKE_END, BRAKE_START, CADENCE, LEVELS, ROOT

CASES = ("baseline", "fixed", "moving", "hold")
CONTRASTS = {
    "fixed_vs_baseline": ("fixed", "baseline"),
    "moving_vs_baseline": ("moving", "baseline"),
    "hold_vs_baseline": ("hold", "baseline"),
    "moving_vs_fixed": ("moving", "fixed"),
    "hold_vs_moving": ("hold", "moving"),
}
WIDTH, PEAK = 0.020, 0.100


def delta(observed, control):
    return 100*(observed/control-1)


def read_runs():
    runs = {tag: {} for tag in LEVELS}
    for tag, (mesh, dt) in LEVELS.items():
        for case in CASES:
            data = json.loads((ROOT/"runs"/f"{tag}_{case}.json").read_text())
            assert data["mesh"] == list(mesh) and data["dt"] == dt and data["case"] == case
            assert np.array_equal(data["stations"], STATIONS)
            runs[tag][case] = data
        shared = round(BRAKE_START/CADENCE)+1
        assert runs[tag]["moving"]["records"][:shared] == runs[tag]["hold"]["records"][:shared]
    return runs


def paired_width(variants, key):
    common = [
        i for i in range(len(STATIONS))
        if all(row["profiles"][i][key] is not None for pair in variants for row in pair)
    ]
    stats = []
    for a, b in variants:
        a, b = (np.array([row["profiles"][i][key] for i in common]) for row in (a, b))
        if not common:
            stats.append(dict(mean=None, median=None))
            continue
        stats.append(dict(mean=float(delta(a.mean(), b.mean())),
                          median=float(np.median(delta(a,b)))))
    return stats, len(common)


def margin(values):
    coarse, fine, half_step = values
    return abs(coarse-fine)+abs(half_step-fine)


def assess(runs):
    false_width = max(c["baseline"]["diagnostic_benchmark"]["max_false_width_gain_pct"]
                      for c in runs.values())
    output = {}
    for name, (treatment, reference) in CONTRASTS.items():
        frames = []
        for sample in range(len(runs["fine_mesh"]["baseline"]["records"])):
            pairs = [[cases[c]["records"][sample] for c in (treatment, reference)]
                     for cases in runs.values()]
            time = pairs[0][0]["t"]
            assert all(r["t"] == time for pair in pairs for r in pair)
            fwhm, n_fwhm = paired_width(pairs, "width")
            integral, n_integral = paired_width(pairs, "integral_width")
            current = [delta(a["annulus_peak_j"],b["annulus_peak_j"]) for a,b in pairs]
            assert all(np.isfinite(current))
            width_error = None if not n_fwhm else margin([r["mean"] for r in fwhm])+false_width
            peak_error = margin(current)
            most_refined = pairs[-1][0]
            pass_at_time = (
                n_fwhm == len(STATIONS) and fwhm[-1]["mean"]-width_error > WIDTH
                and current[-1]+peak_error <= PEAK
            )
            frames.append(dict(
                t=time, fwhm=fwhm, integral_width=integral, peak_current=current,
                fwhm_margin_pp=width_error, peak_margin_pp=peak_error,
                n_fwhm=n_fwhm, n_integral=n_integral, gate_pass=pass_at_time,
                treated_center_y=most_refined["center"][1], treated_speed=most_refined["velocity"],
            ))
        output[name] = frames
    return output


def near_controls(runs):
    output = {}
    for tag in ("archive_mesh", "fine_mesh"):
        near = json.loads((ROOT/"runs"/f"{tag}_fixed_near.json").read_text())
        cases = runs[tag]
        assert near["mesh"] == cases["baseline"]["mesh"] and near["dt"] == cases["baseline"]["dt"]
        stop = cases["hold"]["records"][-1]["center"]
        output[tag] = []
        frames = (near["records"], cases["baseline"]["records"], cases["hold"]["records"])
        for fixed, absent, hold in zip(*frames, strict=True):
            assert fixed["center"] == stop and fixed["velocity"] == 0
            assert fixed["t"] == absent["t"] == hold["t"]
            row = {"t": fixed["t"]}
            for key, reference in (("near_vs_baseline", absent), ("hold_vs_near", fixed)):
                treatment = fixed if key == "near_vs_baseline" else hold
                fwhm, n = paired_width([(treatment, reference)], "width")
                integral, ni = paired_width([(treatment, reference)], "integral_width")
                row[key] = dict(fwhm=fwhm[0], integral_width=integral[0],
                                n_fwhm=n, n_integral=ni, peak_current=float(delta(
                                    treatment["annulus_peak_j"], reference["annulus_peak_j"])))
            output[tag].append(row)
    return output


def plot(traces, near):
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, layout="constrained")
    fig.suptitle("Spherical-core effect before the X-point crossing", fontsize=17, weight="bold")
    colors = {"fixed": "#527953", "moving": "#25668a", "hold": "#aa492b"}
    for case, color in colors.items():
        data = traces[f"{case}_vs_baseline"]
        t = [r["t"] for r in data]
        for axis, diagnostic, key, support in (
            (axes[0], "fwhm", "mean", "n_fwhm"),
            (axes[1], "integral_width", "median", "n_integral"),
        ):
            amounts = [r[diagnostic][-1][key] if r[support] >= 27 else np.nan for r in data]
            axis.plot(t, amounts, label=case.capitalize(), color=color, lw=2)
        axes[2].plot(t, [r["peak_current"][-1] for r in data], color=color, lw=2,
                     label=case.capitalize())
        if case == "hold":
            for axis in axes:
                axis.axvspan(BRAKE_START, BRAKE_END, color="#9b7659", alpha=0.12, lw=0)
    for ax, title in zip(axes, (
        "Mean half-maximum width", "Median width containing the central 50% of positive current",
        "Peak signed sheet current in the full sampled annulus",
    ), strict=True):
        ax.set_title(title)
        ax.set_ylabel("Change vs no core (%)")
        ax.grid(axis="y", alpha=0.23)
    time = [r["t"] for r in near]
    rows = [r["near_vs_baseline"] for r in near]
    for axis, values in zip(axes, (
        [r["fwhm"]["mean"] for r in rows], [r["integral_width"]["median"] for r in rows],
        [r["peak_current"] for r in rows],
    ), strict=True):
        axis.plot(time, values, color="#563e73", linestyle="--", linewidth=1.35,
                  label="Fixed at stopping point")
    axes[0].axhline(WIDTH, ls="--", lw=1.0, color="#3e4346")
    axes[2].axhline(PEAK, ls="--", lw=1.0, color="#3e4346")
    axes[2].set_yscale("symlog", linthresh=0.2)
    axes[0].legend(frameon=False, ncols=2)
    axes[2].set_xlabel("Normalized time")
    fig.savefig(ROOT/"runs"/"core_effect.png", dpi=170)
    plt.close(fig)


def main():
    runs = read_runs()
    results = assess(runs)
    stationary_near = near_controls(runs)
    output = dict(levels=list(LEVELS), width_pct_gate_exclusive=WIDTH,
                  peak_current_pct_gate_inclusive=PEAK, contrasts=results,
                  stationary_at_stop=stationary_near)
    (ROOT/"runs"/"summary.json").write_text(json.dumps(output, indent=2, allow_nan=False)+"\n")
    plot(results, stationary_near["fine_mesh"])
    for contrast, trace in results.items():
        print(contrast, "passing times", [round(r["t"],4) for r in trace if r["gate_pass"]])
        for i in (20,24,28,32,40,48):
            row=trace[i]
            print(round(row["t"],4), row["n_fwhm"], row["fwhm"][-1],
                  row["n_integral"], row["integral_width"][-1],
                  round(row["peak_current"][-1],5), round(row["peak_margin_pp"],5))


if __name__ == "__main__":
    main()
