"""Bound the toroidal actuator requirement while holding the target orbit."""

import json

import numpy as np
from scipy.optimize import linprog

from coil_basis import basis
from equilibrium import read_geqdsk
from fields import FieldMap, RADIUS, ROOT
from orbit import G, I_LIMIT
from reachable_approach import DISTANCE

SAMPLES = 144
DIFFERENCE_STEP = .00025


def evaluate():
    case = json.loads((ROOT / "runs/reachable_approach.json").read_text())["input_case"]
    _, _, _, _, field, gradient = read_geqdsk(ROOT / "reference/g158103.03796")
    center = np.array([RADIUS, case["reference_height_m"]])
    reference_field = field(*center)
    normal = reference_field[[2, 0]] * [1, -1]
    normal *= np.sign(normal[0]) / np.linalg.norm(normal)
    radius, height = center - DISTANCE * normal
    ambient = (field(radius, height), gradient(radius, height))
    ambient_gradient = ambient[1] @ ambient[0] / np.linalg.norm(ambient[0])
    desired_transverse = np.array([ambient_gradient[0], G / case["kappa_Am2_kg"]])
    indices = [0, 2]
    phases = np.linspace(0, 2 * np.pi, SAMPLES, endpoint=False)
    points = np.column_stack((np.full(SAMPLES, radius), phases, np.full(SAMPLES, height)))
    offsets = DIFFERENCE_STEP * np.diag([1., 1. / radius, 1.])
    coil_fields = [basis(points, 96)]
    for offset in offsets:
        coil_fields.append((basis(points + offset, 96) - basis(points - offset, 96)) / (2 * DIFFERENCE_STEP))
    load = case["drag_at_nominal_speed_T_m"]
    rows = []
    for phase, local_response in zip(phases, np.stack(coil_fields, axis=1)):
        base, response = FieldMap.linear_response((*ambient, local_response))
        matrix = response[:, :12] * I_LIMIT[:12]
        scale = 1000.
        transverse = matrix[indices] * scale
        required = (desired_transverse - base[indices]) * scale
        for direction in (1, -1):
            optimum = linprog(-direction * matrix[1] * scale, A_eq=transverse, b_eq=required,
                              bounds=(-1., 1.), method="highs")
            if not optimum.success and optimum.status != 2:
                raise ArithmeticError(optimum.message)
            if optimum.success:
                np.testing.assert_allclose(transverse @ optimum.x, required, atol=1e-6)
            available = float(-optimum.fun / scale) if optimum.success else None
            rows.append(dict(phase_deg=float(np.rad2deg(phase)), direction=direction,
                             tangential_only_T_m=float(abs(matrix[1]).sum()),
                             tangential_with_transverse_trim_T_m=available,
                             supplemental_deficit_T_m=None if available is None else max(0., load - available)))
    results = {}
    for direction in (1, -1):
        subset = [row for row in rows if row["direction"] == direction]
        deficits = [row["supplemental_deficit_T_m"] for row in subset
                    if row["supplemental_deficit_T_m"] is not None]
        results[str(direction)] = dict(trim_feasible_phases=len(deficits), most_needed_T_m=max(deficits, default=None),
                                       mean_needed_T_m=float(np.mean(deficits)) if deficits else None)
    payload = dict(target_RZ_m=[float(radius), float(height)], phase_samples=SAMPLES,
                   drag_magnitude_T_m=load, circular_speed_m_s=float(np.sqrt(
                       -radius * ambient_gradient[0] * case["kappa_Am2_kg"])),
                   assumptions="Instantaneous linear vacuum response, independent 1.6 kA I-coil channels. "
                   "Exact transverse force for a circular orbit at the target. No current dynamics.",
                   summary=results, phases=rows)
    (ROOT / "runs/supplemental_authority.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "phases"}, indent=2))


if __name__ == "__main__":
    evaluate()
