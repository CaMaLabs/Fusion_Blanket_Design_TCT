"""Compare static and phase-synchronized coils on constrained and free orbits."""

import json

import numpy as np

from fields import HALF_WIDTH, RADIUS, ROOT, TWO_PI


I_LIMIT = np.array([1600.] * 12 + [0.] * 6)
OPTIMISTIC_LIMIT = np.full(18, 5000.)
ZERO = np.zeros(18)
G = 9.80665
TOROIDAL_WEIGHT = np.array([1., 0.7, 1.15])
REGULARIZATION = 0.00012**2 * np.eye(3)
PLANE = json.loads((ROOT / "reference/prior_plane_summary.json").read_text())["relaxed_plane"]
FIXED = np.array(PLANE["currents_A"])


def propulsion(response, limit, direction=1):
    # Smooth saturation avoids discontinuous current reversals at zero coupling.
    leverage = response[..., 1, :] * limit
    scale = 0.20 * np.maximum(np.max(np.abs(leverage), axis=-1, keepdims=True), 1e-12)
    return direction * limit * np.tanh(leverage / scale)


def ring_test(field_map, samples=720):
    angles = np.linspace(0, TWO_PI, samples, endpoint=False)
    local = [field_map.local(np.array([RADIUS, p, field_map.height])) for p in angles]
    response = np.array([field_map.linear_response(v)[1] for v in local])
    orders = np.fft.fftfreq(samples, d=1 / samples)[:, None]
    fixed_force = np.array([field_map.force(point, FIXED)[1] for point in local])
    static_mean = float(fixed_force.mean())
    assert abs(static_mean) < 3e-7
    test = {"fixed_mean_gradient_T_m": static_mean, "results": []}
    for label, limit in (("independent_I_1.6kA", I_LIMIT), ("independent_IC_5kA", OPTIMISTIC_LIMIT)):
        command = propulsion(response, limit)
        harmonic = np.fft.fft(command, axis=0)
        for laps_hz in (1, 10, 100, 300):
            for cutoff_hz in (30, 100, 300, None):
                filtered = harmonic if cutoff_hz is None else harmonic / (1 + 1j * orders * laps_hz / cutoff_hz)
                current = np.fft.ifft(filtered, axis=0).real
                positive = np.array([field_map.force(v, i)[1] for v, i in zip(local, current)])
                negative = np.array([field_map.force(v, -i)[1] for v, i in zip(local, current)])
                # For reverse travel the command goes past the same points in reverse order.
                # Use a conjugate transfer function to apply the filter in the time direction.
                if cutoff_hz is not None:
                    reverse = -np.fft.ifft(harmonic / (1 - 1j * orders * laps_hz / cutoff_hz), axis=0).real
                    negative = np.array([field_map.force(v, i)[1] for v, i in zip(local, reverse)])
                test["results"].append(dict(
                    config=label, laps_hz=laps_hz, cutoff_hz=cutoff_hz,
                    mean_tangential_T_m=float(positive.mean()), min_tangential_T_m=float(positive.min()),
                    positive_force_fraction=float(np.mean(positive > 0)),
                    forward_work_per_moment_T=float(positive.mean() * RADIUS * TWO_PI),
                    reverse_work_per_moment_T=float(-negative.mean() * RADIUS * TWO_PI),
                    max_slew_A_s=float(np.abs(np.fft.ifft(1j * orders * TWO_PI * laps_hz * filtered,
                                                         axis=0).real).max()),
                ))
    return test


def guided_currents(local, state, desired_height, desired_speed, gravity, limit, drag=0.,
                    weights=TOROIDAL_WEIGHT, hold_angular_momentum=False, reference=None):
    radius, _, height, radial_speed, toroidal_speed, vertical_speed = state
    base, response = local
    reference_radius, reference_vr, reference_vz = RADIUS, 0., 0.
    radial_feedforward, vertical_feedforward = 0., 0.
    if reference is not None:
        position, velocity, acceleration, momentum, momentum_rate = reference
        reference_radius, desired_height = position
        reference_vr, reference_vz = velocity
        radial_feedforward, vertical_feedforward = acceleration
        toroidal = momentum_rate / radius + .30 * (momentum / radius - toroidal_speed) + drag
    elif hold_angular_momentum:
        toroidal = 0.30 * (RADIUS * desired_speed / radius - toroidal_speed) + drag
    else:
        toroidal = 0.30 * (desired_speed - toroidal_speed) + radial_speed * toroidal_speed / radius + drag
    desired = np.array([
        radial_feedforward - toroidal_speed**2 / radius
        - 0.55 * (radius - reference_radius) - 0.45 * (radial_speed - reference_vr),
        toroidal,
        gravity + vertical_feedforward - .55 * (height - desired_height) - .80 * (vertical_speed - reference_vz),
    ])
    matrix = response * (limit[None, :] * weights[:, None])
    target = (desired - base) * weights
    fraction = np.clip(matrix.T @ np.linalg.solve(matrix @ matrix.T + REGULARIZATION, target), -1, 1)
    # Reallocate residual to unsaturated windings using the same local response.
    for _ in range(2):
        available = np.abs(fraction) < 0.999
        free = matrix[:, available]
        correction = free.T @ np.linalg.solve(free @ free.T + REGULARIZATION, target - matrix @ fraction)
        fraction[available] = np.clip(fraction[available] + correction, -1, 1)
    return limit * fraction


def trajectory(field_map, mode, kappa, has_gravity, phase_deg, launch,
               cutoff_hz, steps_per_lap=288, laps=3, traces=False, balanced_height=None,
               drag_per_moment=0., compensate_drag=False, direction=1, kick_at_lap_one_m_s=None,
               guide_weights=TOROIDAL_WEIGHT, hold_angular_momentum=False, reference_at=None,
               control_policy=None, supplemental_toroidal_gradient=0.):
    """Advance a free point dipole using time scaled by sqrt(moment / mass)."""
    if direction not in (-1, 1):
        raise ValueError("Direction must be +1 or -1")
    if not np.isfinite(supplemental_toroidal_gradient) or supplemental_toroidal_gradient < 0.:
        raise ValueError("Supplemental gradient capacity must be finite and nonnegative")
    height, speed = field_map.height, field_map.balance_speed
    if balanced_height is not None:
        height = balanced_height
        speed = np.sqrt(-RADIUS * field_map.ambient(RADIUS, height)[1][0])
    gravity = G / kappa if has_gravity else 0.
    phase = np.deg2rad(phase_deg)
    d_r, d_z, speed_scale = launch
    desired_speed = direction * speed
    state = np.array([RADIUS + d_r, phase, height + d_z, 0., desired_speed * speed_scale, 0.])
    if mode == "guided_5kA_IC":
        limit = OPTIMISTIC_LIMIT
    else:
        limit = I_LIMIT
    if supplemental_toroidal_gradient:
        if control_policy is None or mode in ("ambient", "fixed_plane_5kA_IC", "drive_1.6kA_I"):
            raise ValueError("Supplemental force requires a guided mode and a control policy")
        limit = np.append(limit, 1.)
    dt = TWO_PI * RADIUS / (steps_per_lap * speed)
    dt_real = dt / np.sqrt(kappa)
    half_decay = 0. if cutoff_hz is None else np.exp(-TWO_PI * cutoff_hz * dt_real / 2)
    decay = half_decay**2

    def drag_at(toroidal_speed):
        return drag_per_moment * toroidal_speed * abs(toroidal_speed) / speed**2

    def target(local, current_state, elapsed_s):
        if mode == "ambient":
            return ZERO
        if mode == "fixed_plane_5kA_IC":
            return FIXED
        response = field_map.linear_response(local)
        if mode == "drive_1.6kA_I":
            return propulsion(response[1], limit, direction)
        drag = drag_at(current_state[4]) if compensate_drag else 0.
        reference = reference_at(elapsed_s) if reference_at is not None else None
        if supplemental_toroidal_gradient:
            base, gradients = response
            response = base, np.column_stack((gradients, [0., supplemental_toroidal_gradient, 0.]))
        if control_policy is not None:
            return control_policy(response, current_state, reference, gravity, drag, limit)
        return guided_currents(response, current_state, height, desired_speed, gravity, limit,
                               drag=drag, weights=guide_weights, hold_angular_momentum=hold_angular_momentum,
                               reference=reference)

    def motion(v, current, local=None):
        radius, _, _, vr, vt, vz = v
        if local is None:
            local = field_map.local(v[:3])
        ar, at, az = field_map.force(local, current[:len(I_LIMIT)])
        if supplemental_toroidal_gradient:
            at += supplemental_toroidal_gradient * current[-1]
        return np.array([vr, vt / radius, vz, ar + vt**2 / radius,
                         at - vr * vt / radius - drag_at(vt), az - gravity])

    current = target(field_map.local(state[:3]), state, 0.)
    radial_peak, vertical_peak = abs(d_r), abs(state[2] - field_map.height)
    peak_current = np.abs(current[:len(I_LIMIT)]).max()
    peak_slew = 0.
    peak_supplemental = abs(supplemental_toroidal_gradient * current[-1])
    visited = [(0., *state)] if traces else []
    cause = "time_limit"
    elapsed = 0.
    kick_time = None
    for step in range(steps_per_lap * (laps + 1)):
        local = field_map.local(state[:3])
        # Predict the midpoint using the current force, then hold the resulting
        # command for one update interval while solving the current lag exactly.
        prior = motion(state, current, local)
        predictor = state + 0.5 * dt * prior
        midpoint = field_map.local(predictor[:3])
        command = target(midpoint, predictor, (step + .5) * dt_real)
        if cutoff_hz is not None:
            current_change = command[:len(I_LIMIT)] - current[:len(I_LIMIT)]
            peak_slew = max(peak_slew, float(TWO_PI * cutoff_hz * np.abs(current_change).max()))
        middle = command + (current - command) * half_decay
        end = command + (current - command) * decay
        k1 = prior if cutoff_hz is not None else motion(state, command, local)
        k2 = motion(state + dt / 2 * k1, middle)
        k3 = motion(state + dt / 2 * k2, middle)
        k4 = motion(state + dt * k3, end)
        state += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        current = end
        elapsed = (step + 1) * dt_real
        laps_travelled = direction * (state[1] - phase) / TWO_PI
        if kick_at_lap_one_m_s is not None and kick_time is None and laps_travelled >= 1:
            state[[3, 4, 5]] += np.asarray(kick_at_lap_one_m_s) / np.sqrt(kappa)
            kick_time = elapsed
        radial_peak = max(radial_peak, abs(state[0] - RADIUS))
        vertical_peak = max(vertical_peak, abs(state[2] - field_map.height))
        peak_current = max(peak_current, np.abs(current[:len(I_LIMIT)]).max())
        if supplemental_toroidal_gradient:
            peak_supplemental = max(peak_supplemental, abs(supplemental_toroidal_gradient * current[-1]))
        if traces:
            visited.append((elapsed, *state))
        if radial_peak > HALF_WIDTH or vertical_peak > HALF_WIDTH:
            cause = "radial_corridor" if radial_peak / HALF_WIDTH >= vertical_peak / HALF_WIDTH else "vertical_corridor"
            break
        if laps_travelled >= laps:
            cause = "completed"
            break

    result = dict(mode=mode, kappa_Am2_kg=kappa, gravity=has_gravity, phase_deg=phase_deg,
                  launch=list(launch), reference_height_m=height, cutoff_hz=cutoff_hz, steps_per_lap=steps_per_lap,
                  outcome=cause, laps=float(laps_travelled), elapsed_s=elapsed, direction=direction,
                  radial_peak_m=float(radial_peak), vertical_peak_m=float(vertical_peak),
                  initial_toroidal_speed_m_s=float(desired_speed * speed_scale * np.sqrt(kappa)),
                  final_toroidal_speed_m_s=float(state[4] * np.sqrt(kappa)),
                  peak_current_A=float(peak_current), peak_slew_A_s=peak_slew if cutoff_hz is not None else None,
                  kick_time_s=kick_time)
    if supplemental_toroidal_gradient:
        result["peak_supplemental_T_m"] = float(peak_supplemental)
    return result, np.array(visited)
