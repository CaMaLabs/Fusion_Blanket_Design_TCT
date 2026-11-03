"""Fiflis/Ruzic 2016 liquid-lithium free-surface stability helpers.

Implements the experimentally anchored *heuristic* boundary published in:
P. Fiflis et al., Nuclear Fusion 56 (2016) 106020,
"Free surface stability of liquid metal plasma facing components".

The paper's equations used here are:

    x = J[kA/m^2] B[T] / (120 * 0.22) + 0.02 v[km/s]^2 / w[mm]   (Eq. 22)
    w_crit[mm] = 15 / x^0.75 + 10 / x^0.5                        (Eq. 23)

Eq. 23 is a fit/guide to the modified shallow-water stability map, not a
universal law. The helper therefore reports domain/extrapolation flags rather
than silently treating it as reactor-validated.

The optional J-B angle correction is a repository adaptation based on the
magnitude of J x B. It is not part of Eq. 22 as printed in the paper.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

REFERENCE_J_KA_M2 = 120.0
REFERENCE_B_T = 0.22
TELS_X_MIN = 0.5
TELS_X_MAX = 3.0
TELS_WIDTH_MIN_MM = 10.0
TELS_WIDTH_MAX_MM = 30.0


@dataclass(frozen=True)
class RuzicInputs:
    current_density_ka_m2: float
    magnetic_field_t: float
    plasma_tangential_velocity_km_s: float
    trench_width_mm: float
    jb_angle_deg: float = 90.0
    wetted: bool = True


@dataclass(frozen=True)
class RuzicResult:
    normalized_plasma_impulse_x: float
    max_stable_width_mm: float
    width_margin_mm: float
    width_margin_fraction: float
    stable_by_eq23: bool
    j_perpendicular_ka_m2: float
    rt_term: float
    kh_term: float
    domain_label: str
    wetting_label: str
    claim_boundary: str


def _finite_nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0; got {value!r}")
    return value


def perpendicular_current_density(current_density_ka_m2: float, jb_angle_deg: float) -> float:
    """Return |J| sin(theta), the current component contributing to |J x B|.

    This orientation correction is a repository extension motivated by the
    paper's discussion of current direction relative to the toroidal field.
    """
    j = _finite_nonnegative("current_density_ka_m2", current_density_ka_m2)
    angle = float(jb_angle_deg)
    if not math.isfinite(angle):
        raise ValueError("jb_angle_deg must be finite")
    return j * abs(math.sin(math.radians(angle)))


def normalized_plasma_impulse(
    current_density_ka_m2: float,
    magnetic_field_t: float,
    plasma_tangential_velocity_km_s: float,
    trench_width_mm: float,
    jb_angle_deg: float = 90.0,
) -> tuple[float, float, float, float]:
    """Evaluate the normalized impulse x from Fiflis et al. Eq. 22.

    Returns (x, J_perp, RT_term, KH_term).
    """
    b = _finite_nonnegative("magnetic_field_t", magnetic_field_t)
    v = _finite_nonnegative(
        "plasma_tangential_velocity_km_s", plasma_tangential_velocity_km_s
    )
    w = _finite_nonnegative("trench_width_mm", trench_width_mm)
    if w <= 0.0:
        raise ValueError("trench_width_mm must be > 0")

    j_perp = perpendicular_current_density(current_density_ka_m2, jb_angle_deg)
    rt_term = (j_perp * b) / (REFERENCE_J_KA_M2 * REFERENCE_B_T)
    kh_term = 0.02 * (v**2) / w
    return rt_term + kh_term, j_perp, rt_term, kh_term


def max_stable_width_mm(normalized_impulse_x: float) -> float:
    """Evaluate Fiflis et al. Eq. 23.

    As x -> 0, the fitted stable width tends to infinity. Returning ``inf`` is
    more useful for an engineering gate than dividing by zero.
    """
    x = _finite_nonnegative("normalized_impulse_x", normalized_impulse_x)
    if x == 0.0:
        return math.inf
    return 15.0 / (x**0.75) + 10.0 / math.sqrt(x)


def plateau_rayleigh_curvature_index(liquid_height_mm: float, radius_of_curvature_mm: float) -> float:
    """Return H/(pi Rc)-1 from Fiflis et al. Eq. 20.

    Positive values indicate the paper's Plateau-Rayleigh ejection criterion is
    met locally. This helper does not infer Rc; a measured/simulated curvature
    must be supplied by the caller.
    """
    h = _finite_nonnegative("liquid_height_mm", liquid_height_mm)
    rc = _finite_nonnegative("radius_of_curvature_mm", radius_of_curvature_mm)
    if rc <= 0.0:
        raise ValueError("radius_of_curvature_mm must be > 0")
    return h / (math.pi * rc) - 1.0


def evaluate(inputs: RuzicInputs) -> RuzicResult:
    x, j_perp, rt_term, kh_term = normalized_plasma_impulse(
        current_density_ka_m2=inputs.current_density_ka_m2,
        magnetic_field_t=inputs.magnetic_field_t,
        plasma_tangential_velocity_km_s=inputs.plasma_tangential_velocity_km_s,
        trench_width_mm=inputs.trench_width_mm,
        jb_angle_deg=inputs.jb_angle_deg,
    )
    w_crit = max_stable_width_mm(x)
    margin_mm = w_crit - inputs.trench_width_mm
    margin_fraction = margin_mm / inputs.trench_width_mm

    in_x = TELS_X_MIN <= x <= TELS_X_MAX
    in_w = TELS_WIDTH_MIN_MM <= inputs.trench_width_mm <= TELS_WIDTH_MAX_MM
    if in_x and in_w:
        domain_label = "WITHIN_FIG7A_PLOTTED_RANGE"
    elif in_x:
        domain_label = "WIDTH_EXTRAPOLATION_FROM_FIG7A"
    else:
        domain_label = "IMPULSE_EXTRAPOLATION_FROM_FIG7A"

    wetting_label = "WETTED_ASSUMPTION" if inputs.wetted else "UNWETTED_OUTSIDE_EQ23_USE_CASE"
    stable = bool(inputs.wetted and inputs.trench_width_mm <= w_crit)

    return RuzicResult(
        normalized_plasma_impulse_x=x,
        max_stable_width_mm=w_crit,
        width_margin_mm=margin_mm,
        width_margin_fraction=margin_fraction,
        stable_by_eq23=stable,
        j_perpendicular_ka_m2=j_perp,
        rt_term=rt_term,
        kh_term=kh_term,
        domain_label=domain_label,
        wetting_label=wetting_label,
        claim_boundary=(
            "Fiflis/Ruzic 2016 reduced surface-retention gate only; does not validate "
            "lithium-current -> plasma-edge actuator transfer or reactor survivability."
        ),
    )


def evaluate_dict(inputs: RuzicInputs) -> dict[str, Any]:
    row = asdict(inputs)
    row.update(asdict(evaluate(inputs)))
    return row
