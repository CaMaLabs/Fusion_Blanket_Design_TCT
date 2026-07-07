#!/usr/bin/env python3
"""Reduced liquid-lithium surface-stability scenario matrix.

This is a deterministic reduced model for ranking follow-up bench-test
priorities. It is not a free-surface MHD solver, lithium material model, or
reactor validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = REPO / "validation_runs" / "liquid_lithium_stability_default"

SCHEMA_VERSION = "1.0"
STATUS = "REDUCED_MODEL_PRIORITIZATION_ONLY"

CSV_FIELDS = [
    "scenario",
    "scenario_family",
    "is_falsification_case",
    "initial_amplitude",
    "growth_decay_rate",
    "final_surface_amplitude",
    "stability_margin",
    "bubble_coalescence_risk_score",
    "vapor_film_risk_score",
    "lithium_retention_score",
    "regime_label",
    "viscosity_damping",
    "magnetic_damping",
    "capillary_stabilization",
    "microtexture_wetting",
    "rewetting_strength",
    "vapor_film_penalty",
    "plasma_shear_damping",
    "bubble_coalescence_suppression",
    "heat_flux_drive",
    "dryout_penalty",
    "surface_drive",
]


@dataclass(frozen=True)
class Scenario:
    scenario: str
    scenario_family: str
    description: str
    initial_amplitude: float = 0.10
    viscosity_damping: float = 0.08
    magnetic_damping: float = 0.10
    capillary_stabilization: float = 0.00
    microtexture_wetting: float = 0.00
    rewetting_strength: float = 0.00
    vapor_film_penalty: float = 0.15
    plasma_shear_damping: float = 0.00
    bubble_coalescence_suppression: float = 0.00
    heat_flux_drive: float = 0.22
    dryout_penalty: float = 0.00
    surface_drive: float = 0.16
    is_falsification_case: bool = False


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _round(value: float) -> float:
    return round(float(value), 10)


def scenario_matrix() -> list[Scenario]:
    """Return the deterministic baseline, mechanism, combined, and failure cases."""
    return [
        Scenario(
            "free_lithium_pool_baseline",
            "baseline",
            "Free lithium pool with no engineered surface confinement.",
        ),
        Scenario(
            "ribbed_substrate",
            "single_mechanism",
            "Macroscopic ribs add geometric retention and modest capillary pinning.",
            capillary_stabilization=0.18,
            microtexture_wetting=0.06,
            rewetting_strength=0.04,
            surface_drive=0.14,
        ),
        Scenario(
            "porous_wick_cps_substrate",
            "single_mechanism",
            "CPS-style porous/wick confinement adds capillary hold-up and bubble suppression.",
            capillary_stabilization=0.42,
            microtexture_wetting=0.18,
            rewetting_strength=0.18,
            bubble_coalescence_suppression=0.22,
            surface_drive=0.12,
        ),
        Scenario(
            "microtextured_high_wetting_surface",
            "single_mechanism",
            "Microtexture and wetting promote rewetting and raise the reduced vapor-blanket threshold.",
            capillary_stabilization=0.20,
            microtexture_wetting=0.42,
            rewetting_strength=0.34,
            bubble_coalescence_suppression=0.10,
            vapor_film_penalty=0.08,
            surface_drive=0.13,
        ),
        Scenario(
            "vapor_film_prone_hot_surface",
            "adverse_baseline",
            "Hot poorly wetting surface where vapor blanketing is expected to dominate.",
            initial_amplitude=0.14,
            magnetic_damping=0.06,
            heat_flux_drive=0.62,
            vapor_film_penalty=0.62,
            surface_drive=0.23,
        ),
        Scenario(
            "argon_cover_gas_only",
            "single_mechanism",
            "Inert cover gas without ionized boundary-layer forcing.",
            viscosity_damping=0.09,
            plasma_shear_damping=0.02,
            bubble_coalescence_suppression=0.04,
            surface_drive=0.155,
        ),
        Scenario(
            "weak_plasma_ion_wind_boundary_layer",
            "single_mechanism",
            "Weak argon plasma/ion-wind boundary-layer shear damping proxy.",
            plasma_shear_damping=0.18,
            bubble_coalescence_suppression=0.08,
            surface_drive=0.145,
        ),
        Scenario(
            "combined_porous_microtexture_plasma",
            "combined",
            "Porous/wick confinement plus high-wetting microtexture plus weak plasma boundary-layer damping.",
            viscosity_damping=0.09,
            magnetic_damping=0.14,
            capillary_stabilization=0.48,
            microtexture_wetting=0.46,
            rewetting_strength=0.40,
            vapor_film_penalty=0.06,
            plasma_shear_damping=0.20,
            bubble_coalescence_suppression=0.30,
            heat_flux_drive=0.20,
            surface_drive=0.10,
        ),
        Scenario(
            "falsification_high_heat_flux_vapor_blanketing",
            "falsification",
            "High heat flux overwhelms rewetting and drives vapor-film domination.",
            initial_amplitude=0.16,
            capillary_stabilization=0.34,
            microtexture_wetting=0.28,
            rewetting_strength=0.24,
            vapor_film_penalty=0.86,
            plasma_shear_damping=0.12,
            bubble_coalescence_suppression=0.10,
            heat_flux_drive=0.92,
            dryout_penalty=0.16,
            surface_drive=0.26,
            is_falsification_case=True,
        ),
        Scenario(
            "falsification_insufficient_wetting",
            "falsification",
            "Texture exists but wetting/rewetting are too weak to retain lithium.",
            initial_amplitude=0.15,
            capillary_stabilization=0.14,
            microtexture_wetting=0.03,
            rewetting_strength=0.02,
            vapor_film_penalty=0.46,
            heat_flux_drive=0.42,
            surface_drive=0.22,
            is_falsification_case=True,
        ),
        Scenario(
            "falsification_excessive_perturbation",
            "falsification",
            "Initial surface displacement is outside the stabilizable range of the reduced model.",
            initial_amplitude=0.72,
            capillary_stabilization=0.44,
            microtexture_wetting=0.34,
            rewetting_strength=0.26,
            plasma_shear_damping=0.18,
            bubble_coalescence_suppression=0.20,
            heat_flux_drive=0.44,
            surface_drive=0.46,
            is_falsification_case=True,
        ),
        Scenario(
            "falsification_plasma_shear_too_weak",
            "falsification",
            "Plasma boundary layer is present but too weak to add meaningful damping.",
            plasma_shear_damping=0.01,
            bubble_coalescence_suppression=0.02,
            heat_flux_drive=0.36,
            vapor_film_penalty=0.34,
            surface_drive=0.21,
            is_falsification_case=True,
        ),
        Scenario(
            "falsification_porous_dryout_saturation",
            "falsification",
            "Porous/wick stabilization is degraded by saturation/dryout.",
            initial_amplitude=0.18,
            capillary_stabilization=0.42,
            microtexture_wetting=0.22,
            rewetting_strength=0.16,
            bubble_coalescence_suppression=0.16,
            heat_flux_drive=0.58,
            vapor_film_penalty=0.50,
            dryout_penalty=0.38,
            surface_drive=0.24,
            is_falsification_case=True,
        ),
        Scenario(
            "falsification_magnetic_damping_absent",
            "falsification",
            "Surface confinement is present but magnetic damping is absent.",
            magnetic_damping=0.00,
            capillary_stabilization=0.24,
            microtexture_wetting=0.18,
            rewetting_strength=0.12,
            plasma_shear_damping=0.05,
            bubble_coalescence_suppression=0.12,
            heat_flux_drive=0.46,
            vapor_film_penalty=0.38,
            surface_drive=0.28,
            is_falsification_case=True,
        ),
    ]


def evaluate_scenario(scenario: Scenario, duration: float = 8.0) -> dict[str, Any]:
    """Evaluate a scenario with a deterministic reduced amplitude/risk model.

    Surface amplitude follows A(t) = A0 exp(rate * t), with rate assembled from
    stabilizing damping terms and destabilizing heat/vapor/bubble/surface terms.
    Risk scores are dimensionless screening proxies. They are calibrated only to
    produce deterministic ordering and explicit falsification cases.
    """
    stabilizing = (
        scenario.viscosity_damping
        + scenario.magnetic_damping
        + 0.95 * scenario.capillary_stabilization
        + 0.70 * scenario.microtexture_wetting
        + 0.70 * scenario.rewetting_strength
        + 0.85 * scenario.plasma_shear_damping
        + 0.55 * scenario.bubble_coalescence_suppression
    )
    destabilizing = (
        scenario.surface_drive
        + 0.62 * scenario.heat_flux_drive
        + 0.92 * scenario.vapor_film_penalty
        + 0.72 * scenario.dryout_penalty
        + 0.58 * scenario.initial_amplitude
    )
    stability_margin = stabilizing - destabilizing
    growth_decay_rate = -0.18 * stability_margin
    final_amplitude = scenario.initial_amplitude * math.exp(growth_decay_rate * duration)

    vapor_risk = _clip(
        0.20
        + 0.72 * scenario.vapor_film_penalty
        + 0.46 * scenario.heat_flux_drive
        + 0.40 * scenario.dryout_penalty
        - 0.36 * scenario.microtexture_wetting
        - 0.34 * scenario.rewetting_strength
        - 0.24 * scenario.capillary_stabilization
    )
    bubble_risk = _clip(
        0.24
        + 0.55 * scenario.surface_drive
        + 0.45 * scenario.initial_amplitude
        + 0.28 * scenario.heat_flux_drive
        - 0.46 * scenario.bubble_coalescence_suppression
        - 0.20 * scenario.microtexture_wetting
        - 0.18 * scenario.capillary_stabilization
        - 0.12 * scenario.plasma_shear_damping
    )
    retention = _clip(
        0.82
        + 0.22 * scenario.capillary_stabilization
        + 0.20 * scenario.microtexture_wetting
        + 0.16 * scenario.rewetting_strength
        + 0.08 * scenario.magnetic_damping
        - 0.34 * final_amplitude
        - 0.30 * vapor_risk
        - 0.18 * bubble_risk
        - 0.20 * scenario.dryout_penalty
    )

    if vapor_risk >= 0.68:
        label = "vapor-film dominated"
    elif bubble_risk >= 0.60:
        label = "bubble-coalescence dominated"
    elif final_amplitude >= 0.38 or stability_margin < -0.18:
        label = "unstable"
    elif stability_margin < 0.10:
        label = "marginal"
    else:
        label = "stable"

    row = asdict(scenario)
    row.update(
        {
            "growth_decay_rate": _round(growth_decay_rate),
            "final_surface_amplitude": _round(final_amplitude),
            "stability_margin": _round(stability_margin),
            "bubble_coalescence_risk_score": _round(bubble_risk),
            "vapor_film_risk_score": _round(vapor_risk),
            "lithium_retention_score": _round(retention),
            "regime_label": label,
        }
    )
    return row


def run_matrix(duration: float = 8.0) -> list[dict[str, Any]]:
    return [evaluate_scenario(scenario, duration=duration) for scenario in scenario_matrix()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})


def _best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda row: (
            float(row["stability_margin"]),
            float(row["lithium_retention_score"]),
            -float(row["vapor_film_risk_score"]),
        ),
    )


def _summarize(rows: list[dict[str, Any]], duration: float) -> dict[str, Any]:
    labels: dict[str, int] = {}
    for row in rows:
        labels[row["regime_label"]] = labels.get(row["regime_label"], 0) + 1
    best = _best(rows)
    baseline = next(row for row in rows if row["scenario"] == "free_lithium_pool_baseline")
    combined = next(row for row in rows if row["scenario"] == "combined_porous_microtexture_plasma")
    falsification_failures = [
        row["scenario"]
        for row in rows
        if row["is_falsification_case"] and row["regime_label"] != "stable"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "duration": duration,
        "scenario_count": len(rows),
        "regime_counts": labels,
        "best_scenario": best["scenario"],
        "baseline_regime": baseline["regime_label"],
        "combined_regime": combined["regime_label"],
        "combined_margin_improvement_vs_baseline": _round(
            float(combined["stability_margin"]) - float(baseline["stability_margin"])
        ),
        "combined_retention_improvement_vs_baseline": _round(
            float(combined["lithium_retention_score"]) - float(baseline["lithium_retention_score"])
        ),
        "falsification_nonstable_cases": falsification_failures,
        "conservative_conclusion": (
            "The reduced model supports prioritizing capillary/porous confinement, wetting microtexture, "
            "argon/plasma boundary-layer damping, and magnetic damping for follow-up bench testing. It does "
            "not show that liquid lithium is stabilized in a reactor."
        ),
        "claim_boundaries": [
            "reduced deterministic screening model only",
            "not free-surface MHD",
            "not liquid-lithium material compatibility validation",
            "not tokamak or reactor validation",
            "not proof of TCT actuation",
        ],
        "cases": rows,
    }


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    rows = summary["cases"]
    best = next(row for row in rows if row["scenario"] == summary["best_scenario"])
    combined = next(row for row in rows if row["scenario"] == "combined_porous_microtexture_plasma")
    vapor_fail = next(row for row in rows if row["scenario"] == "falsification_high_heat_flux_vapor_blanketing")
    lines = [
        "# Liquid Lithium Surface Stability Reduced-Model Report",
        "",
        f"- Status: `{summary['status']}`",
        f"- Scenario count: `{summary['scenario_count']}`",
        f"- Best reduced-model scenario: `{summary['best_scenario']}`",
        "",
        "## What This Adds",
        "",
        "This module translates three outside stabilization mechanisms into a deterministic reduced scenario matrix:",
        "",
        "- ionized-gas / plasma-assisted surface damping as a boundary-layer shear damping proxy,",
        "- liquid-surface stabilization / surfactant-like bubble coalescence suppression as a bubble-risk proxy,",
        "- micro/nanotexture and capillary rewetting as vapor-film and retention proxies.",
        "",
        "It is a bench-test prioritization layer, not a reactor or tokamak-grade validation result.",
        "",
        "## Key Results",
        "",
        "| Scenario | Regime | Margin | Final amplitude | Bubble risk | Vapor risk | Retention |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['scenario']}` | {row['regime_label']} | "
            f"{float(row['stability_margin']):.3f} | {float(row['final_surface_amplitude']):.3f} | "
            f"{float(row['bubble_coalescence_risk_score']):.3f} | "
            f"{float(row['vapor_film_risk_score']):.3f} | "
            f"{float(row['lithium_retention_score']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Strongest Result",
            "",
            f"`{best['scenario']}` had the highest stability-margin ordering in this reduced matrix "
            f"with margin `{float(best['stability_margin']):.3f}` and retention score "
            f"`{float(best['lithium_retention_score']):.3f}`.",
            "",
            "The combined porous + microtexture + plasma case is the intended positive-control case. "
            f"It improved stability margin by `{summary['combined_margin_improvement_vs_baseline']:.3f}` "
            "relative to the free-pool baseline.",
            "",
            "## Falsification Behavior",
            "",
            f"The high-heat-flux vapor-blanketing case produced `{vapor_fail['regime_label']}` behavior "
            f"with vapor risk `{float(vapor_fail['vapor_film_risk_score']):.3f}`.",
            "",
            "Non-stable falsification cases:",
            "",
        ]
    )
    for case in summary["falsification_nonstable_cases"]:
        lines.append(f"- `{case}`")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- No Navier-Stokes/free-surface MHD solve.",
            "- No lithium wetting chemistry, corrosion, evaporation, impurity, or material-compatibility model.",
            "- No acoustic model.",
            "- No tokamak geometry, neutron environment, or plasma-edge coupling.",
            "- Coefficients are transparent screening weights, not measured lithium parameters.",
            "",
            "## Conservative Conclusion",
            "",
            summary["conservative_conclusion"],
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(path: Path) -> None:
    path.write_text(
        """# Liquid Lithium Surface Stability Module

This validation layer is a deterministic reduced model for ranking
liquid-lithium surface-stability bench-test ideas. It is intentionally separate
from the BOUT++, M3D-C1, FreeGSNKE, FAIR-MAST, and Dedalus current-sheet
validation artifacts.

Run:

```bash
python scripts/run_liquid_lithium_stability.py \\
  --run-dir validation_runs/liquid_lithium_stability_default
```

Outputs:

- `liquid_lithium_stability_results.csv`
- `liquid_lithium_stability_summary.json`
- `LIQUID_LITHIUM_STABILITY_REPORT.md`

Claim boundary: this module supports prioritizing capillary/porous
confinement, wetting microtexture, inert-gas/plasma boundary damping, and
magnetic damping for follow-up bench tests. It does not validate liquid lithium
surface stability in a reactor.
""",
        encoding="utf-8",
    )


def _run_regression_checks(summary: dict[str, Any]) -> None:
    rows = {row["scenario"]: row for row in summary["cases"]}
    required = set(CSV_FIELDS) | {"description"}
    for name, row in rows.items():
        missing = required - row.keys()
        if missing:
            raise AssertionError(f"{name} missing fields: {sorted(missing)}")
    if rows["combined_porous_microtexture_plasma"]["regime_label"] != "stable":
        raise AssertionError("combined positive-control case should be stable")
    if rows["falsification_high_heat_flux_vapor_blanketing"]["regime_label"] != "vapor-film dominated":
        raise AssertionError("high-heat-flux falsification should be vapor-film dominated")
    if float(rows["combined_porous_microtexture_plasma"]["stability_margin"]) <= float(
        rows["free_lithium_pool_baseline"]["stability_margin"]
    ):
        raise AssertionError("combined case should improve stability margin vs baseline")
    if float(rows["falsification_plasma_shear_too_weak"]["stability_margin"]) >= 0.10:
        raise AssertionError("weak-plasma falsification should not pass as stable")
    stable_falsifications = [
        name
        for name, row in rows.items()
        if row["is_falsification_case"] and row["regime_label"] == "stable"
    ]
    if stable_falsifications:
        raise AssertionError(f"falsification cases unexpectedly stable: {stable_falsifications}")


def maybe_write_plot(run_dir: Path, rows: list[dict[str, Any]]) -> str | None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None
    names = [row["scenario"].replace("_", "\n") for row in rows]
    margins = [float(row["stability_margin"]) for row in rows]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(len(rows)), margins, color=["#4c78a8" if m >= 0 else "#e45756" for m in margins])
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_ylabel("reduced stability margin")
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=7)
    fig.tight_layout()
    path = run_dir / "stability_margin_by_scenario.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--check", action="store_true", help="run deterministic regression checks")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = run_matrix(duration=args.duration)
    summary = _summarize(rows, duration=args.duration)
    if args.check:
        _run_regression_checks(summary)

    _write_csv(run_dir / "liquid_lithium_stability_results.csv", rows)
    (run_dir / "liquid_lithium_stability_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_report(run_dir / "LIQUID_LITHIUM_STABILITY_REPORT.md", summary)
    _write_readme(run_dir / "README.md")
    if not args.no_plots:
        plot_path = maybe_write_plot(run_dir, rows)
        if plot_path:
            summary["plot"] = plot_path
            (run_dir / "liquid_lithium_stability_summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
            )
    print(json.dumps({k: summary[k] for k in ("status", "scenario_count", "best_scenario")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
