#!/usr/bin/env python3
"""Plot and summarize Dedalus current-sheet benchmark diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float_series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([float(row[key]) for row in rows], dtype=float)


def _case_summary(case: str, rows: list[dict[str, Any]], case_dir: Path) -> dict[str, Any]:
    time = _float_series(rows, "time")
    aspect = _float_series(rows, "aspect_ratio")
    delta = _float_series(rows, "delta")
    energy = _float_series(rows, "magnetic_energy")
    island_count = _float_series(rows, "island_count_proxy")
    onset = None
    hits = np.where(island_count >= 3)[0]
    if len(hits):
        onset = float(time[int(hits[0])])
    summary_path = case_dir / "summary.json"
    run_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "case": case,
        "diagnostic_rows": len(rows),
        "time_start": float(time[0]),
        "time_end": float(time[-1]),
        "min_delta": float(np.min(delta)),
        "max_aspect_ratio": float(np.max(aspect)),
        "time_to_secondary_island_proxy": run_summary.get("time_to_secondary_island_proxy", onset),
        "initial_island_count_proxy": run_summary.get("initial_island_count_proxy"),
        "initial_magnetic_energy": float(energy[0]),
        "final_magnetic_energy": float(energy[-1]),
        "magnetic_energy_decay_fraction": float(1.0 - energy[-1] / energy[0]) if energy[0] else None,
        "final_island_count_proxy": int(island_count[-1]),
    }


def _plot(run_dir: Path, case_rows: dict[str, list[dict[str, Any]]]) -> None:
    import matplotlib.pyplot as plt

    plot_dir = run_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    metrics = [
        ("delta", "Current-sheet half-thickness delta"),
        ("aspect_ratio", "Sheet aspect ratio L/delta"),
        ("reconnection_rate_proxy", "Reconnection rate proxy eta max|J|"),
        ("magnetic_energy", "Magnetic energy"),
        ("island_count_proxy", "Island/plasmoid count proxy"),
        ("max_abs_J", "Max |J|"),
    ]
    for key, ylabel in metrics:
        fig, ax = plt.subplots(figsize=(7, 4), dpi=140)
        for case, rows in case_rows.items():
            ax.plot(_float_series(rows, "time"), _float_series(rows, key), label=case)
        ax.set_xlabel("time")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / f"{key}.png")
        plt.close(fig)

    for case in case_rows:
        snapshot_path = run_dir / case / "snapshots.npz"
        if not snapshot_path.exists():
            continue
        data = np.load(snapshot_path)
        if len(data["times"]) == 0:
            continue
        for idx, label in ((0, "initial"), (-1, "final")):
            fig, ax = plt.subplots(figsize=(5, 4), dpi=140)
            image = ax.imshow(data["psi"][idx].T, origin="lower", aspect="auto")
            ax.set_title(f"{case} {label} psi, t={data['times'][idx]:.3f}")
            fig.colorbar(image, ax=ax, label="psi")
            fig.tight_layout()
            fig.savefig(plot_dir / f"{case}_{label}_psi.png")
            plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("validation_runs/dedalus_current_sheet_default"))
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    case_rows: dict[str, list[dict[str, Any]]] = {}
    for case_dir in sorted(path for path in args.run_dir.iterdir() if path.is_dir()):
        diagnostics = case_dir / "diagnostics.csv"
        if diagnostics.exists():
            case_rows[case_dir.name] = _read_csv(diagnostics)
    if not case_rows:
        raise SystemExit(f"No case diagnostics found under {args.run_dir}")

    summaries = [_case_summary(case, rows, args.run_dir / case) for case, rows in case_rows.items()]
    if not args.no_plots:
        _plot(args.run_dir, case_rows)
    output = {
        "artifact_type": "dedalus_reduced_mhd_toy_diagnostics",
        "not_reactor_claim": True,
        "not_tokamak_validation": True,
        "cases": summaries,
    }
    (args.run_dir / "diagnostics_summary.json").write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
