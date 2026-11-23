"""Compare the probe orbit with the published DIII-D shot 158103 rotation fit."""

import json

import numpy as np
from scipy.optimize import brentq

from equilibrium import read_geqdsk
from fields import HALF_WIDTH, RADIUS, ROOT


def rotation(flux):
    """Lyons et al. (2017), Eq. 1 and the fit in Fig. 2, in rad/s."""
    axis, far, zero, width = 110_000., -40_000., .915, .025
    center = zero + .01
    theta = lambda psi: 1 - np.tanh((psi - center) / width)
    slope = (axis - far + 2 * far / theta(zero)) / zero
    return .5 * (axis - far - slope * flux) * theta(flux) + far


def main():
    archived = json.loads((ROOT / "runs/weight_shape_fine_compound_speed_scaled_drag_momentum.json").read_text())
    case = next(row for row in archived["trajectories"] if row["load"] == "same_area" and row["direction"] == 1)
    metadata, _, _, flux, _, _ = read_geqdsk(ROOT / "reference/g158103.03796")
    height = case["reference_height_m"]
    original_height = archived["original_height_m"]
    radii = RADIUS + np.linspace(-HALF_WIDTH, HALF_WIDTH, 81)
    heights = original_height + np.linspace(-HALF_WIDTH, HALF_WIDTH, 81)
    r, z = np.meshgrid(radii, heights)
    corridor_flux = flux(r, z)
    corridor_flow = r * rotation(corridor_flux)
    reference_flux = float(flux(RADIUS, height))
    zero_radius = brentq(lambda radius: flux(radius, height) - .915, RADIUS, RADIUS + .15)
    nominal_probe_speed = abs(case["initial_toroidal_speed_m_s"] / case["launch"][2])
    fit_speed = float(RADIUS * rotation(reference_flux))
    relative = sorted(abs(fit_speed - sign * nominal_probe_speed) for sign in (1, -1))
    radius_at_speed = lambda speed: brentq(
        lambda radius: radius * rotation(float(flux(radius, height))) - speed,
        zero_radius - .01, zero_radius + .01,
    )
    band = sorted(radius_at_speed(speed) for speed in (-300., 300.))
    patch_m = .21
    time_unit_s = patch_m / nominal_probe_speed / .60
    smallest_step_s = time_unit_s * .0015625
    assert abs(rotation(.915)) < 1e-9
    result = dict(
        source="https://m3dc1.pppl.gov/Papers/lyons_PPCF_17.pdf",
        profile="Experimental E×B toroidal rotation fit, not total ion flow",
        geometry=metadata, radius_m=RADIUS, height_m=height, flux_at_orbit=reference_flux,
        flow_at_orbit_m_s=fit_speed, probe_speed_m_s=nominal_probe_speed,
        reference_component_relative_speed_m_s=relative,
        corridor_flux_range=[float(corridor_flux.min()), float(corridor_flux.max())],
        corridor_fit_speed_m_s=[float(corridor_flow.min()), float(corridor_flow.max())],
        zero_rotation_radius_at_trim_height_m=float(zero_radius),
        zero_rotation_outside_corridor_m=float(zero_radius - RADIUS - HALF_WIDTH),
        abs_fit_speed_below_300_m_s_radius_range=band,
        abs_fit_speed_below_300_m_s_radial_width_m=band[1] - band[0],
        previous_patch_m=patch_m,
        component_based_patch_transit_s=sorted(patch_m / speed for speed in relative),
        previous_smallest_replay_step_s=smallest_step_s,
    )
    (ROOT / "runs/shot_flow.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
