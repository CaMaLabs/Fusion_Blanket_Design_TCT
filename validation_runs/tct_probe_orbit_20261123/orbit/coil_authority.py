"""Estimate ideal tangential authority around the reference orbit."""

import json

import numpy as np

from coil_basis import basis
from equilibrium import read_geqdsk
from fields import RADIUS, ROOT


def main():
    case = json.loads((ROOT / "runs/reachable_approach.json").read_text())["input_case"]
    _, _, _, _, field, _ = read_geqdsk(ROOT / "reference/g158103.03796")
    height = case["reference_height_m"]
    unit = field(RADIUS, height)
    unit /= np.linalg.norm(unit)
    phases = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    points = np.column_stack((np.full_like(phases, RADIUS), phases, np.full_like(phases, height)))
    step = .00025
    displacement = np.array([0., step / RADIUS, 0.])
    derivative = (basis(points + displacement, 96) - basis(points - displacement, 96)) @ unit / (2 * step)
    authority = 1600. * np.abs(derivative[:, :12]).sum(axis=1)
    drag = case["drag_at_nominal_speed_T_m"]
    report = dict(
        reference_height_m=height, phase_samples=len(phases), imposed_drag_T_m=drag,
        ideal_available_T_m=dict(min=float(authority.min()), mean=float(authority.mean()),
                                 max=float(authority.max())),
        fraction_of_phases_at_or_above_drag=float(np.mean(authority >= drag)),
        assumption="Linear vacuum-field response, all available I-coil authority used tangentially.",
    )
    (ROOT / "runs/coil_authority.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
