#!/usr/bin/env python3
"""Run an Ubuntu-friendly Fiflis/Ruzic 2016 lithium surface-retention sweep."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from liquid_lithium_stability.ruzic_fiflis_2016 import RuzicInputs, evaluate_dict

DEFAULT_RUN_DIR = REPO / "validation_runs" / "ruzic_li_surface_gate_default"

FIELDS = [
    "current_density_ka_m2",
    "magnetic_field_t",
    "plasma_tangential_velocity_km_s",
    "trench_width_mm",
    "jb_angle_deg",
    "wetted",
    "j_perpendicular_ka_m2",
    "rt_term",
    "kh_term",
    "normalized_plasma_impulse_x",
    "max_stable_width_mm",
    "width_margin_mm",
    "width_margin_fraction",
    "stable_by_eq23",
    "domain_label",
    "wetting_label",
    "claim_boundary",
]


def _floats(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def build_cases(args: argparse.Namespace) -> list[RuzicInputs]:
    cases: list[RuzicInputs] = []
    for j in _floats(args.current_density):
        for b in _floats(args.magnetic_field):
            for v in _floats(args.velocity):
                for w in _floats(args.width):
                    for angle in _floats(args.jb_angle):
                        cases.append(
                            RuzicInputs(
                                current_density_ka_m2=j,
                                magnetic_field_t=b,
                                plasma_tangential_velocity_km_s=v,
                                trench_width_mm=w,
                                jb_angle_deg=angle,
                                wetted=not args.unwetted,
                            )
                        )
    return cases


def write_report(path: Path, rows: list[dict]) -> None:
    stable = sum(bool(row["stable_by_eq23"]) for row in rows)
    in_domain = sum(row["domain_label"] == "WITHIN_FIG7A_PLOTTED_RANGE" for row in rows)
    worst = min(rows, key=lambda row: float(row["width_margin_fraction"]))
    best = max(rows, key=lambda row: float(row["width_margin_fraction"]))
    text = f"""# Fiflis/Ruzic 2016 Lithium Surface Gate

Status: `SURFACE_RETENTION_REDUCED_GATE_ONLY`

Cases: {len(rows)}
Stable by Eq. 23 with wetted assumption: {stable}
Within Figure 7A plotted x/width range: {in_domain}

## Most restrictive case

- J: {worst['current_density_ka_m2']} kA/m^2
- B: {worst['magnetic_field_t']} T
- tangential plasma velocity: {worst['plasma_tangential_velocity_km_s']} km/s
- trench width: {worst['trench_width_mm']} mm
- J-B angle: {worst['jb_angle_deg']} deg
- x: {worst['normalized_plasma_impulse_x']:.6g}
- Eq. 23 max stable width: {worst['max_stable_width_mm']:.6g} mm
- width margin: {worst['width_margin_fraction']:.3%}
- domain: {worst['domain_label']}

## Largest margin case

- x: {best['normalized_plasma_impulse_x']:.6g}
- Eq. 23 max stable width: {best['max_stable_width_mm']:.6g} mm
- width margin: {best['width_margin_fraction']:.3%}

## Claim boundary

This runner uses Fiflis et al. (Nucl. Fusion 56, 106020, 2016) Eq. 22 and
Eq. 23 as a liquid-surface retention/ejection screening gate. The optional
J-B angle correction uses |J x B| and is a repository adaptation. This does
**not** supply the missing liquid-current -> edge-plasma transfer function and
does **not** close a reactor engineering validation gate.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--current-density", default="84,120,150,300")
    parser.add_argument("--magnetic-field", default="0.22,2,5")
    parser.add_argument("--velocity", default="0,6,15.9,65")
    parser.add_argument("--width", default="2,6,10,14,22,26")
    parser.add_argument("--jb-angle", default="0,15,45,90")
    parser.add_argument("--unwetted", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [evaluate_dict(case) for case in build_cases(args)]

    csv_path = run_dir / "ruzic_li_surface_gate.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{key: row[key] for key in FIELDS} for row in rows])

    summary = {
        "status": "SURFACE_RETENTION_REDUCED_GATE_ONLY",
        "case_count": len(rows),
        "stable_case_count": sum(bool(row["stable_by_eq23"]) for row in rows),
        "within_fig7a_range_count": sum(
            row["domain_label"] == "WITHIN_FIG7A_PLOTTED_RANGE" for row in rows
        ),
        "source": "Fiflis et al., Nucl. Fusion 56 (2016) 106020, Eq. 22-23",
        "claim_boundary": rows[0]["claim_boundary"] if rows else "",
    }
    (run_dir / "ruzic_li_surface_gate_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_report(run_dir / "RUZIC_LI_SURFACE_GATE_REPORT.md", rows)

    if args.check:
        ref22 = evaluate_dict(RuzicInputs(120.0, 0.22, 0.0, 22.0, 90.0, True))
        ref26 = evaluate_dict(RuzicInputs(120.0, 0.22, 0.0, 26.0, 90.0, True))
        assert abs(float(ref22["max_stable_width_mm"]) - 25.0) < 1e-12
        assert ref22["stable_by_eq23"] is True
        assert ref26["stable_by_eq23"] is False

    print(json.dumps(summary, indent=2))
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
