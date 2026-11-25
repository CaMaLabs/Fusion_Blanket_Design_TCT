"""Recompute heat- and pressure-release comparisons from saved histories."""

import argparse
import json
from math import fsum, isclose
from pathlib import Path


ENERGIES = ("kinetic", "magnetic", "thermal")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integrate_sampled_power(rows):
    return fsum(.5*(left["exhaust_power"] + right["exhaust_power"])*(right["time"] - left["time"])
                for left, right in zip(rows, rows[1:]))


def balance_residual(rows):
    highest = 0.
    for row in rows:
        cumul = row["cumulative"]
        energy_change = fsum(row[key] - rows[0][key] for key in ENERGIES)
        scale = abs(cumul["body_work"]) + cumul["penalty_slip"] + cumul["exhaust"]
        if scale > 0.:
            residual = fsum((energy_change, -cumul["body_work"], cumul["penalty_slip"], cumul["exhaust"]))
            highest = max(highest, abs(residual)/scale)
    return highest


def audit_release(path):
    receipt = json.loads(path.read_text())
    cases = receipt["results"]
    controls = {case["level"]: case["rows"] for case in cases if case["case"] == "unforced"}
    print(f"{path.name}  sink center {receipt['choices']['exhaust_center']:.2f}")
    print("Case                           Level  Escape change    Peak change      Peak time")
    worst_integral_error = worst_balance_error = 0.
    for case in cases:
        name, level, rows = case["case"], case["level"], case["rows"]
        context = f"{path.name} {name} level {level}"
        reference = controls[level]
        require(case["minimum_heat"] > 0., f"Nonpositive thermal energy density in {context}")
        require([r["time"] for r in rows] == [r["time"] for r in reference], f"Unmatched times in {context}")
        require(all(rows[0][key] == reference[0][key] for key in ENERGIES),
                f"Unmatched initial energies in {context}")
        require(isclose(rows[-1]["time_ms"], receipt["horizon_ms"]), f"Wrong horizon in {context}")
        totals = [r["cumulative"]["exhaust"] for r in rows]
        require(all(0 <= a <= b for a, b in zip(totals, totals[1:])), f"Invalid cumulative exhaust in {context}")
        total = totals[-1]
        integral = integrate_sampled_power(rows)
        integral_error = abs(integral/total - 1.)
        balance_error = balance_residual(rows)
        worst_integral_error = max(worst_integral_error, integral_error)
        worst_balance_error = max(worst_balance_error, balance_error)
        require(integral_error < .001 and balance_error < .001, f"Exhaust or energy-budget audit failed in {context}")

        peak = max(rows, key=lambda row: row["exhaust_power"])
        reference_peak = max(row["exhaust_power"] for row in reference)
        escape_change = 100.*(total/reference[-1]["cumulative"]["exhaust"] - 1.)
        peak_change = 100.*(peak["exhaust_power"]/reference_peak - 1.)
        summary = case["summary"]
        for key, expected in (("escape_energy", total), ("escape_change_pct", escape_change),
                              ("peak_power", peak["exhaust_power"]), ("peak_change_pct", peak_change),
                              ("peak_time_ms", peak["time_ms"])):
            require(isclose(summary[key], expected, rel_tol=1e-10, abs_tol=1e-10), f"{key} mismatch in {context}")
        sampled_change = 100.*(integral/integrate_sampled_power(reference) - 1.)
        require(abs(sampled_change - escape_change) < .1, f"Sampled exhaust change disagrees in {context}")
        end = "  end of window" if peak is rows[-1] else ""
        print(f"{name:30} {level:>3} {escape_change:>13.5f}% {peak_change:>13.5f}% {peak['time_ms']:>11.4f} ms{end}")
    print(f"Maximum sampled integration difference {100*worst_integral_error:.6g}%"
          f" and maximum energy-balance residual {100*worst_balance_error:.6g}%")


def audit_heat(path):
    receipt = json.loads(path.read_text())
    cases = receipt["results"]
    early_index = receipt["theta"].index(1.)
    fine = max(case["level"] for case in cases)
    print(f"\n{path.name}  fraction reaching both plates at theta=1 on the fine grid")
    for case in cases:
        early = []
        for target in case["targets"]:
            cumulative = target["cumulative_both_plate_fractions"]
            final = fsum(target["eventual_plate_fractions"])
            unresolved = target["unresolved_fraction"]
            require(abs(final + unresolved - 1.) < 1e-10, f"Unbalanced plate fractions in {case['case']}")
            require(all(-1e-10 <= a <= b+1e-10 <= final+2e-10 for a, b in zip(cumulative, cumulative[1:])),
                    f"Invalid time-resolved plate fractions in {case['case']}")
            early.append(cumulative[early_index])
        if case["level"] == fine:
            print(f"{case['case']:30} {100*min(early):.2f}% to {100*max(early):.2f}%")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_receipts", nargs="+", type=Path)
    parser.add_argument("--heat", type=Path)
    args = parser.parse_args()
    for path in args.release_receipts:
        audit_release(path)
    if args.heat:
        audit_heat(args.heat)


if __name__ == "__main__":
    main()
