from __future__ import annotations

import math
from typing import Iterable

from .models import Evaluation


OBJECTIVE_DIRECTIONS = {
    "width_gain": "max",
    "peak_j_reduction": "max",
    "high_j_reduction": "max",
    "reconnection_reduction": "max",
    "low_energy_perturbation": "max",
    "low_net_current_perturbation": "max",
    "ruzic_margin": "max",
}


def make_objectives(evaluation: Evaluation) -> dict[str, float]:
    stage = evaluation.stages[-1] if evaluation.stages else None
    m = stage.metrics if stage else {}

    def finite(value, default):
        try:
            x = float(value)
            return x if math.isfinite(x) else default
        except Exception:
            return default

    width = finite(m.get("mean_active_width_gain_pct"), -1e6)
    peak = -finite(m.get("mean_active_peak_j_change_pct"), 1e6)
    high = -finite(m.get("mean_active_high_j_change_pct"), 1e6)
    recon = -finite(m.get("peak_reconnection_rate_change_pct"), 1e6)
    magnetic_energy = abs(finite(m.get("max_abs_magnetic_energy_change_pct"), 1e6))
    kinetic_energy = abs(finite(m.get("max_abs_kinetic_energy_change_pct"), 1e6))
    # Penalize whichever energy channel moves more strongly, so a momentum/shear
    # candidate cannot look artificially cheap because magnetic energy stays small.
    energy = -max(magnetic_energy, kinetic_energy)
    current = -abs(finite(m.get("max_abs_toroidal_current_change_pct"), 1e6))

    p = evaluation.physical_gate
    if p.get("classification") == "LITHIUM_RUZIC_SURFACE_GATE_PASS":
        ruzic = finite(p.get("width_margin_fraction"), -1e6)
    elif p.get("classification") == "LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED":
        ruzic = -1e3
    elif p.get("classification") == "LITHIUM_MAPPING_NOT_APPLICABLE":
        ruzic = -1e2
    else:
        ruzic = -1e6

    depth_bonus = {
        "none": 0.0,
        "impulse": 1.0,
        "sustained": 2.0,
        "full": 3.0,
    }.get(evaluation.deepest_stage, 0.0)
    return {
        "width_gain": width + 0.001 * depth_bonus,
        "peak_j_reduction": peak,
        "high_j_reduction": high,
        "reconnection_reduction": recon,
        "low_energy_perturbation": energy,
        "low_net_current_perturbation": current,
        "ruzic_margin": ruzic,
    }


def dominates(a: Evaluation, b: Evaluation) -> bool:
    if a.feasible and not b.feasible:
        return True
    if b.feasible and not a.feasible:
        return False
    av, bv = a.objectives, b.objectives
    return all(
        av.get(k, -math.inf) >= bv.get(k, -math.inf)
        for k in OBJECTIVE_DIRECTIONS
    ) and any(
        av.get(k, -math.inf) > bv.get(k, -math.inf)
        for k in OBJECTIVE_DIRECTIONS
    )


def pareto_front(items: Iterable[Evaluation]) -> list[Evaluation]:
    rows = list(items)
    return [
        candidate
        for i, candidate in enumerate(rows)
        if not any(i != j and dominates(other, candidate) for j, other in enumerate(rows))
    ]
