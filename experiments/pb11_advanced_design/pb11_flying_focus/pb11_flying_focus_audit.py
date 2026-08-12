#!/usr/bin/env python3
"""PB11 flying-focus resonance-occupancy audit.

This is a deliberately separate screening model for the Fusion_Blanket_Design_TCT
p-B11 advanced-design branch.  It does NOT predict reactor gain, ignition, or an
absolute p-11B reaction rate.  It tests whether a programmable flying-focus
proton injector/rephaser can keep a nonthermal proton packet near the 675-keV
p-11B resonance more efficiently than fixed-energy / non-rephased alternatives.

The nuclear response is represented by a normalized two-resonance proxy.  The
675-keV feature is the primary target and a smaller ~148-keV feature is retained
so the repository's existing 120-keV operating point is not artificially scored
as zero.  Stopping loss, straggling, trapping fraction, and FF energy spread are
explicit sweep parameters because a validated low-energy TFF scaling law does
not yet exist.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

SEED = 6750411
DEFAULT_N = 120_000
DEFAULT_CYCLES = 32

# Repository baseline imported from:
# experiments/pb11_advanced_design/m3dc1_handoff_best/pb11_surrogate_manifest.json
REPO_BASELINE = {
    "proton_energy_center_keV": 120.0,
    "proton_energy_spread_pct": 8.0,
    "proton_window_fraction": 1.0,
    "proton_burnup_fraction": 0.23033,
    "proton_loss_fraction": 0.118,
    "effective_proton_path_length_passes": 419246.468,
    "hardware_recirc_passes": 100000.0,
    "pB11_alpha_yield": 2.363,
    "pB11_gross_power": 3.28,
    "pB11_net_delta": 2.048,
    "pb11_support_driver_power": 0.098,
    "pb11_support_recirc_power": 0.198,
}


@dataclass(frozen=True)
class Case:
    name: str
    initial_keV: float
    spread_pct: float
    hold_target_keV: float | None = None
    ff_rephase_target_keV: float | None = None
    ff_trap_fraction: float = 0.0
    ff_rephase_spread_pct: float = 3.7
    ff_target_jitter_keV: float = 0.0
    sync_sheet: bool = False


@dataclass
class Result:
    case: str
    cycles: int
    initial_keV: float
    initial_spread_pct: float
    mean_resonance_score: float
    cumulative_resonance_exposure: float
    mean_primary_window_fraction: float
    final_primary_window_fraction: float
    final_mean_keV: float
    final_std_keV: float
    rephase_delivered_keV_per_initial_proton: float
    injector_delivered_keV_per_initial_proton: float
    total_delivered_keV_per_initial_proton: float
    exposure_per_delivered_MeV: float
    relative_exposure_vs_autoresonant_120: float
    relative_exposure_vs_conventional_675: float
    cycles_primary_window_gt_50pct: int
    cycles_resonance_score_gt_50pct: int


def resonance_proxy(E_keV: np.ndarray) -> np.ndarray:
    """Normalized p-11B resonance proxy; not an evaluated nuclear cross section."""
    E = np.asarray(E_keV, dtype=float)
    # Broad primary resonance around 675 keV plus the lower-energy secondary feature.
    primary = np.exp(-0.5 * ((E - 675.0) / 105.0) ** 2)
    secondary = 0.30 * np.exp(-0.5 * ((E - 148.0) / 32.0) ** 2)
    shoulder = 0.08 * np.exp(-0.5 * ((E - 350.0) / 115.0) ** 2)
    return np.clip(primary + secondary + shoulder, 0.0, 1.0)


def window_fraction(E: np.ndarray, lo: float = 550.0, hi: float = 800.0) -> float:
    return float(np.mean((E >= lo) & (E <= hi)))


def _reset_distribution(
    rng: np.random.Generator,
    E: np.ndarray,
    mask: np.ndarray,
    target_keV: float,
    spread_pct: float,
    jitter_keV: float,
) -> float:
    """Reset selected particles to a target packet and return delivered keV."""
    if not np.any(mask):
        return 0.0
    target = target_keV
    if jitter_keV > 0:
        shot_target = target + rng.normal(0.0, jitter_keV)
    else:
        shot_target = target
    sigma = max(0.25, abs(shot_target) * spread_pct / 100.0)
    before = E[mask].copy()
    after = rng.normal(shot_target, sigma, size=int(mask.sum()))
    after = np.clip(after, 1.0, None)
    delivered = float(np.maximum(after - before, 0.0).sum())
    E[mask] = after
    return delivered


def run_case(
    case: Case,
    *,
    n: int,
    cycles: int,
    stopping_loss_keV: float,
    straggling_keV: float,
    rng_seed: int,
) -> Dict[str, object]:
    rng = np.random.default_rng(rng_seed)
    E = rng.normal(case.initial_keV, case.initial_keV * case.spread_pct / 100.0, size=n)
    E = np.clip(E, 1.0, None)

    cumulative_exposure = 0.0
    score_series: List[float] = []
    window_series: List[float] = []
    rephase_delivered = 0.0
    injector_delivered = float(np.maximum(E, 0.0).sum())

    for cycle in range(cycles):
        # Synchronized FF+sheet mode rephases immediately before the reaction sheet.
        if case.sync_sheet and case.ff_rephase_target_keV is not None:
            selected = rng.random(n) < case.ff_trap_fraction
            rephase_delivered += _reset_distribution(
                rng,
                E,
                selected,
                case.ff_rephase_target_keV,
                case.ff_rephase_spread_pct,
                case.ff_target_jitter_keV,
            )

        scores = resonance_proxy(E)
        score = float(scores.mean())
        win = window_fraction(E)
        score_series.append(score)
        window_series.append(win)
        cumulative_exposure += score

        # Every sheet encounter imposes a user-sweepable stopping/straggling burden.
        # This is intentionally not claimed as a stopping-power calculation.
        loss = rng.normal(stopping_loss_keV, straggling_keV, size=n)
        E = np.clip(E - np.maximum(loss, 0.0), 1.0, None)

        # Existing autoresonant hold: idealized reset to the repository target.
        if case.hold_target_keV is not None:
            mask = np.ones(n, dtype=bool)
            rephase_delivered += _reset_distribution(
                rng,
                E,
                mask,
                case.hold_target_keV,
                case.spread_pct,
                0.0,
            )

        # FF rephase occurs after the sheet unless explicitly synchronized above.
        if (not case.sync_sheet) and case.ff_rephase_target_keV is not None:
            selected = rng.random(n) < case.ff_trap_fraction
            rephase_delivered += _reset_distribution(
                rng,
                E,
                selected,
                case.ff_rephase_target_keV,
                case.ff_rephase_spread_pct,
                case.ff_target_jitter_keV,
            )

    total_delivered = injector_delivered + rephase_delivered
    result = {
        "case": case.name,
        "cycles": cycles,
        "initial_keV": case.initial_keV,
        "initial_spread_pct": case.spread_pct,
        "mean_resonance_score": float(np.mean(score_series)),
        "cumulative_resonance_exposure": float(cumulative_exposure),
        "mean_primary_window_fraction": float(np.mean(window_series)),
        "final_primary_window_fraction": float(window_series[-1]),
        "final_mean_keV": float(E.mean()),
        "final_std_keV": float(E.std()),
        "rephase_delivered_keV_per_initial_proton": rephase_delivered / n,
        "injector_delivered_keV_per_initial_proton": injector_delivered / n,
        "total_delivered_keV_per_initial_proton": total_delivered / n,
        "exposure_per_delivered_MeV": cumulative_exposure / max(total_delivered / n / 1000.0, 1e-12),
        "cycles_primary_window_gt_50pct": int(sum(v >= 0.5 for v in window_series)),
        "cycles_resonance_score_gt_50pct": int(sum(v >= 0.5 for v in score_series)),
        "score_series": score_series,
        "window_series": window_series,
    }
    return result


def default_cases() -> List[Case]:
    return [
        Case(
            "autoresonant_hold_120keV",
            initial_keV=120.0,
            spread_pct=8.0,
            hold_target_keV=120.0,
        ),
        Case(
            "conventional_inject_675keV",
            initial_keV=675.0,
            spread_pct=8.0,
        ),
        Case(
            "ff_inject_675keV_3p7pct",
            initial_keV=675.0,
            spread_pct=3.7,
        ),
        Case(
            "ff_rephase_675keV",
            initial_keV=675.0,
            spread_pct=3.7,
            ff_rephase_target_keV=675.0,
            ff_trap_fraction=0.85,
            ff_rephase_spread_pct=3.7,
            ff_target_jitter_keV=10.0,
        ),
        Case(
            "ff_rephase_sync_sheet_675keV",
            initial_keV=675.0,
            spread_pct=3.7,
            ff_rephase_target_keV=675.0,
            ff_trap_fraction=0.92,
            ff_rephase_spread_pct=3.7,
            ff_target_jitter_keV=6.0,
            sync_sheet=True,
        ),
    ]


def run_matrix(n: int, cycles: int, stopping_loss_keV: float, straggling_keV: float) -> List[Dict[str, object]]:
    raw = [
        run_case(
            c,
            n=n,
            cycles=cycles,
            stopping_loss_keV=stopping_loss_keV,
            straggling_keV=straggling_keV,
            rng_seed=SEED + i * 101,
        )
        for i, c in enumerate(default_cases())
    ]
    base = next(r for r in raw if r["case"] == "autoresonant_hold_120keV")
    conv = next(r for r in raw if r["case"] == "conventional_inject_675keV")
    for r in raw:
        r["relative_exposure_vs_autoresonant_120"] = r["cumulative_resonance_exposure"] / max(base["cumulative_resonance_exposure"], 1e-12)
        r["relative_exposure_vs_conventional_675"] = r["cumulative_resonance_exposure"] / max(conv["cumulative_resonance_exposure"], 1e-12)
    return raw


def sensitivity_sweep(n: int, cycles: int) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    idx = 0
    for loss in (10.0, 20.0, 35.0, 50.0):
        for trap in (0.30, 0.45, 0.60, 0.75, 0.85, 0.95):
            for spread in (3.7, 6.0, 10.0, 15.0):
                for jitter in (0.0, 10.0, 25.0, 50.0):
                    c = Case(
                        "sensitivity",
                        initial_keV=675.0,
                        spread_pct=spread,
                        ff_rephase_target_keV=675.0,
                        ff_trap_fraction=trap,
                        ff_rephase_spread_pct=spread,
                        ff_target_jitter_keV=jitter,
                    )
                    r = run_case(
                        c,
                        n=n,
                        cycles=cycles,
                        stopping_loss_keV=loss,
                        straggling_keV=max(2.0, 0.20 * loss),
                        rng_seed=SEED + 10_000 + idx,
                    )
                    rows.append({
                        "stopping_loss_keV": loss,
                        "trap_fraction": trap,
                        "spread_pct": spread,
                        "jitter_keV": jitter,
                        "mean_resonance_score": float(r["mean_resonance_score"]),
                        "cumulative_resonance_exposure": float(r["cumulative_resonance_exposure"]),
                        "mean_primary_window_fraction": float(r["mean_primary_window_fraction"]),
                        "rephase_delivered_keV_per_initial_proton": float(r["rephase_delivered_keV_per_initial_proton"]),
                        "exposure_per_delivered_MeV": float(r["exposure_per_delivered_MeV"]),
                    })
                    idx += 1
    return rows


def efficiency_table(best: Dict[str, object]) -> List[Dict[str, float]]:
    delivered = float(best["total_delivered_keV_per_initial_proton"])
    exposure = float(best["cumulative_resonance_exposure"])
    rows = []
    for eta in (0.01, 0.02, 0.05, 0.10, 0.20, 0.30):
        optical_MeV = delivered / 1000.0 / eta
        rows.append({
            "optical_to_proton_efficiency": eta,
            "optical_input_MeV_per_initial_proton": optical_MeV,
            "resonance_exposure_per_optical_MeV": exposure / optical_MeV,
        })
    return rows


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="pb11_flying_focus_results")
    ap.add_argument("--particles", type=int, default=DEFAULT_N)
    ap.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    ap.add_argument("--stopping-loss-kev", type=float, default=20.0)
    ap.add_argument("--straggling-kev", type=float, default=4.0)
    ap.add_argument("--sensitivity-particles", type=int, default=12_000)
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    matrix = run_matrix(args.particles, args.cycles, args.stopping_loss_kev, args.straggling_kev)
    summary_fields = [
        "case", "cycles", "initial_keV", "initial_spread_pct",
        "mean_resonance_score", "cumulative_resonance_exposure",
        "mean_primary_window_fraction", "final_primary_window_fraction",
        "final_mean_keV", "final_std_keV",
        "injector_delivered_keV_per_initial_proton",
        "rephase_delivered_keV_per_initial_proton",
        "total_delivered_keV_per_initial_proton", "exposure_per_delivered_MeV",
        "relative_exposure_vs_autoresonant_120", "relative_exposure_vs_conventional_675",
        "cycles_primary_window_gt_50pct", "cycles_resonance_score_gt_50pct",
    ]
    write_csv(out / "case_summary.csv", matrix, summary_fields)

    cycle_rows = []
    for r in matrix:
        for i, (score, win) in enumerate(zip(r["score_series"], r["window_series"]), start=1):
            cycle_rows.append({"case": r["case"], "cycle": i, "resonance_score": score, "primary_window_fraction": win})
    write_csv(out / "cycle_history.csv", cycle_rows, ["case", "cycle", "resonance_score", "primary_window_fraction"])

    sens = sensitivity_sweep(args.sensitivity_particles, args.cycles)
    write_csv(out / "sensitivity.csv", sens, list(sens[0].keys()))

    best = next(r for r in matrix if r["case"] == "ff_rephase_sync_sheet_675keV")
    eff = efficiency_table(best)
    write_csv(out / "optical_efficiency_sensitivity.csv", eff, list(eff[0].keys()))

    conv = next(r for r in matrix if r["case"] == "conventional_inject_675keV")
    auto = next(r for r in matrix if r["case"] == "autoresonant_hold_120keV")
    ff_efficiency_ratio_to_conventional = float(conv["exposure_per_delivered_MeV"]) / float(best["exposure_per_delivered_MeV"])
    ff_efficiency_ratio_to_autoresonant = float(auto["exposure_per_delivered_MeV"]) / float(best["exposure_per_delivered_MeV"])
    threshold_rows = []
    for reference_eff in (0.05, 0.10, 0.20, 0.30, 0.50):
        threshold_rows.append({
            "reference_driver_efficiency": reference_eff,
            "ff_efficiency_needed_to_match_conventional_675": reference_eff * ff_efficiency_ratio_to_conventional,
            "ff_efficiency_needed_to_match_autoresonant_120": reference_eff * ff_efficiency_ratio_to_autoresonant,
        })
    write_csv(out / "driver_efficiency_thresholds.csv", threshold_rows, list(threshold_rows[0].keys()))

    # Compact robustness classification over the sensitivity grid.
    strong = [r for r in sens if r["mean_resonance_score"] >= 0.75 and r["mean_primary_window_fraction"] >= 0.75]
    acceptable = [r for r in sens if r["mean_resonance_score"] >= 0.60 and r["mean_primary_window_fraction"] >= 0.60]
    payload = {
        "model": "PB11 flying-focus resonance-occupancy audit v1",
        "disclaimer": "Screening surrogate only; not a reactor-gain, stopping-power, cross-section, PIC, or MHD calculation.",
        "seed": SEED,
        "particles": args.particles,
        "cycles": args.cycles,
        "nominal_stopping_loss_keV_per_sheet": args.stopping_loss_kev,
        "nominal_straggling_keV": args.straggling_kev,
        "repository_baseline": REPO_BASELINE,
        "cases": [{k: v for k, v in r.items() if k not in ("score_series", "window_series")} for r in matrix],
        "robustness": {
            "sensitivity_cases": len(sens),
            "strong_cases": len(strong),
            "strong_fraction": len(strong) / len(sens),
            "acceptable_cases": len(acceptable),
            "acceptable_fraction": len(acceptable) / len(sens),
            "min_mean_resonance_score": min(float(r["mean_resonance_score"]) for r in sens),
            "max_mean_resonance_score": max(float(r["mean_resonance_score"]) for r in sens),
            "min_mean_primary_window_fraction": min(float(r["mean_primary_window_fraction"]) for r in sens),
            "max_mean_primary_window_fraction": max(float(r["mean_primary_window_fraction"]) for r in sens),
        },
        "driver_efficiency_threshold": {
            "ff_efficiency_as_fraction_of_conventional_675_efficiency": ff_efficiency_ratio_to_conventional,
            "ff_efficiency_as_fraction_of_autoresonant_120_efficiency": ff_efficiency_ratio_to_autoresonant,
            "meaning": "Within this resonance-exposure surrogate, FF rephasing only needs this fraction of the reference driver's proton-energy efficiency to match its exposure per source-energy input."
        },
        "interpretation_guardrails": [
            "The 3.7% FF spread is anchored to the published high-energy TFF simulation, not demonstrated at 675 keV.",
            "Stopping loss and straggling are sweep parameters, not SRIM/PIC-derived values for the reactor geometry.",
            "The normalized resonance proxy preserves the 675-keV and ~148-keV features but is not an evaluated absolute cross section.",
            "Optical-to-proton efficiency is intentionally left as a sensitivity rather than assumed.",
            "Native M3DC1 does not model these FF or p-B11 kinetic effects in the current repository.",
        ],
    }
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
