"""Measure the signed plasma-current sheet along its tracked local normal."""
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.ndimage import map_coordinates, spline_filter

from source.sweep_mhd import CORE_RADIUS, LENGTH, MASK_HALF_WIDTH

ANGLES = 2 * np.pi * np.arange(12) / 12
RADII = (0.42, 0.55, 0.70)
STATIONS = np.vstack([
    np.column_stack((radius * np.cos(ANGLES), 0.17 + radius * np.sin(ANGLES)))
    for radius in RADII
])
SLOPE_STEP = 0.025
GUARD_RADIUS = CORE_RADIUS * (1 + MASK_HALF_WIDTH)
VERTICAL = np.linspace(-0.58, 0.58, 801)
NORMAL = np.linspace(-0.62, 0.62, 901)


def sampler(current):
    coefficients = spline_filter(current, order=5, mode="grid-wrap")
    scale = np.asarray(current.shape)

    def sample(points):
        index = (((points / LENGTH + 0.5) % 1) * scale).reshape(-1, 3).T
        return map_coordinates(
            coefficients, index, order=5, mode="grid-wrap", prefilter=False
        ).reshape(points.shape[:-1])

    return sample


def peaks(profiles, offsets, limit):
    step = offsets[1] - offsets[0]
    choices = np.flatnonzero(np.abs(offsets) < limit)
    i = choices[0] + np.argmax(profiles[:, choices], axis=1)
    p = np.arange(len(profiles))
    a, b, c = profiles[p, i - 1], profiles[p, i], profiles[p, i + 1]
    curvature = a - 2 * b + c
    fraction = np.divide(a - c, 2 * curvature, out=np.zeros_like(a), where=curvature < 0)
    fraction = np.clip(fraction, -0.5, 0.5)
    height = b + 0.5 * (c - a) * fraction + 0.5 * curvature * fraction**2
    valid = (i > choices[0]) & (i < choices[-1]) & (curvature < 0) & (height > 0)
    return offsets[i] + fraction * step, height, i, valid


def interpolate_crossing(profile, lower_idx, level):
    a, b = profile[[lower_idx, lower_idx + 1]]
    return NORMAL[lower_idx] + (level - a) / (b - a) * (NORMAL[1] - NORMAL[0])


def read_sheet(current, center, *, sample=None):
    if sample is None:
        sample = sampler(current)
    centers = np.column_stack((STATIONS[:, 0], np.zeros(len(STATIONS)), STATIONS[:, 1]))
    shifts = SLOPE_STEP * np.array([[0, 0, 0], [1, 0, 0], [-1, 0, 0],
                                   [0, 0, 1], [0, 0, -1]])
    vertical_points = centers[None, :, None, :] + shifts[:, None, None, :]
    vertical_points = vertical_points + VERTICAL[None, None, :, None] * [0, 1, 0]
    values = sample(vertical_points).reshape(-1, len(VERTICAL))
    ridge, _, _, ridge_valid = peaks(values, VERTICAL, 0.37)
    ridge = ridge.reshape(5, -1)
    centers[:, 1] = ridge[0]
    slope_x, slope_z = (ridge[1] - ridge[2]) / (2*SLOPE_STEP), (ridge[3] - ridge[4]) / (2*SLOPE_STEP)
    unit_normal = np.column_stack((-slope_x, np.ones(len(STATIONS)), -slope_z))
    unit_normal /= np.linalg.norm(unit_normal, axis=1)[:, None]
    profiles = sample(centers[:, None, :] + unit_normal[:, None, :] * NORMAL[:, None])
    offset, strength, high_index, peak_valid = peaks(profiles, NORMAL, 0.18)
    # Width of the central 50% of positive current in a fixed normal interval.
    current_window = abs(NORMAL) <= 0.42
    window = NORMAL[current_window]
    cumulative = cumulative_trapezoid(profiles[:, current_window].clip(min=0), window,
                                     axis=1, initial=0)
    output = []
    for i, profile in enumerate(profiles):
        diagnostics = dict(ridge_y=float(ridge[0, i]), normal_y=float(unit_normal[i, 1]),
                           width=None, peak_current=None, integral_width=None)
        output.append(diagnostics)
        if not peak_valid[i] or not np.all(ridge_valid.reshape(5, -1)[:, i]):
            continue
        difference = centers[i] - center
        nearest = -np.dot(difference, unit_normal[i])
        s_integral = np.clip(nearest, window[0], window[-1])
        total = cumulative[i, -1]
        if total > 0 and np.linalg.norm(difference + s_integral * unit_normal[i]) >= GUARD_RADIUS:
            lower_q, upper_q = np.interp([0.25 * total, 0.75 * total], cumulative[i], window)
            diagnostics["integral_width"] = float(upper_q - lower_q)
        level = 0.5 * strength[i]
        maximum = high_index[i]
        lower = np.flatnonzero(profile[:maximum] < level)
        upper = np.flatnonzero(profile[maximum:] < level) + maximum
        if not lower.size or not upper.size:
            continue
        left = interpolate_crossing(profile, lower[-1], level)
        right = interpolate_crossing(profile, upper[0] - 1, level)
        if not (left < offset[i] < right):
            continue
        # Common exclusion around the trajectory, including the virtual no-core path.
        s = np.clip(nearest, left, right)
        if np.linalg.norm(difference + s * unit_normal[i]) < GUARD_RADIUS:
            continue
        diagnostics.update(width=float(right - left), peak_current=float(strength[i]))
    return output


def verify(shape):
    y = (np.arange(shape[1]) / shape[1] - 0.5) * LENGTH[1]
    ideal = np.arcsin(2 * 0.26 * np.arccosh(np.sqrt(2)))
    center = np.array([0.0, 0.0, 0.17])

    def observed(shift, width):
        thickness = np.sin(width) / (2 * np.arccosh(np.sqrt(2)))
        profile = 1 / np.cosh(np.sin(2*(y-shift)) / (2*thickness))**2
        current = np.broadcast_to(profile[None, :, None], shape).copy()
        values = read_sheet(current, center)
        assert all(row["width"] is not None for row in values)
        return float(np.mean([row["width"] for row in values]))

    zero = observed(0, ideal)
    displaced = [observed(shift, ideal) for shift in (0.017, 0.042, 0.083)]
    broadened = [observed(shift, ideal * 1.0002) for shift in (0.017, 0.042, 0.083)]
    false_pp = max(abs(x/zero - 1)*100 for x in displaced)
    recovered = [(b / a - 1) * 100 for a, b in zip(displaced, broadened, strict=True)]
    assert abs(zero/ideal - 1) < 0.001
    assert max(abs(x - 0.02) for x in recovered) < 0.002
    return dict(known_width=float(ideal), recovered_width=zero,
                max_false_width_gain_pct=false_pp, recovered_0p02pct_gains=recovered)
