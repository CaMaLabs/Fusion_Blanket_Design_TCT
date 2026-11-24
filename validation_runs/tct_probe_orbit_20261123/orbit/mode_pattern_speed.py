"""Estimate signed toroidal pattern speed from synchronous magnetic diagnostics."""

import argparse
import json

import numpy as np


def estimate(time, angles, signals, radius, mode, max_mode, min_amplitude):
    time = np.asarray(time, dtype=float)
    angles = np.asarray(angles, dtype=float)
    signals = np.asarray(signals, dtype=float)
    if (time.ndim != 1 or angles.ndim != 1 or signals.shape != (time.size, angles.size)
            or time.size < 8 or not all(np.isfinite(x).all() for x in (time, angles, signals))):
        raise ValueError("Provide finite time_s, phi_rad and signal[time, probe] arrays")
    spacing = np.diff(time)
    if (not np.all(spacing > 0.) or not np.isfinite(radius) or radius <= 0.
            or not 1 <= mode <= max_mode or not np.isfinite(min_amplitude) or min_amplitude < 0.):
        raise ValueError("Time must increase and radius, modes and amplitude floor must be valid")
    harmonics = np.arange(1, max_mode + 1) * angles[:, None]
    design = np.column_stack((np.ones_like(angles), np.cos(harmonics), np.sin(harmonics)))
    condition = np.linalg.cond(design)
    if len(angles) <= design.shape[1] or condition > 100:
        raise ValueError("Probe geometry cannot resolve these modes with a spatial residual")

    coeff, *_ = np.linalg.lstsq(design, signals.T, rcond=None)
    in_phase, quadrature = coeff[mode], coeff[max_mode + mode]
    phasor = in_phase + 1j * quadrature
    amplitude = abs(phasor)
    residual = (signals.T - design @ coeff)
    noise = np.linalg.norm(residual, axis=0) / np.sqrt(len(angles) - design.shape[1])
    numerical_floor = 10 * np.finfo(float).eps * np.max(abs(signals))
    usable = amplitude > np.maximum(3 * noise, max(min_amplitude, numerical_floor))
    neighbors = usable[:-1] & usable[1:] & (spacing <= 2 * np.median(spacing))
    breaks = np.flatnonzero(~neighbors) + 1
    segments = np.split(np.arange(len(time)), breaks)
    chosen = max(segments, key=lambda idx: time[idx[-1]] - time[idx[0]])
    if len(chosen) < 8 or not usable[chosen].all():
        raise ValueError("No contiguous, sufficiently resolved mode phase in the requested window")

    times = time[chosen]
    phase = np.unwrap(np.angle(phasor[chosen]))
    weights = amplitude[chosen]**2
    centered_time = times - np.average(times, weights=weights)
    centered_phase = phase - np.average(phase, weights=weights)
    angular_frequency = float(np.dot(weights * centered_time, centered_phase)
                              / np.dot(weights * centered_time, centered_time))
    errors = centered_phase - angular_frequency * centered_time
    toroidal_rate = angular_frequency / mode
    return dict(
        signed_mode_frequency_hz=angular_frequency / (2 * np.pi),
        signed_toroidal_pattern_speed_m_s=radius * toroidal_rate,
        radius_m=radius, toroidal_mode=mode, max_fitted_mode=max_mode, probe_count=len(angles),
        geometry_condition=float(condition), fitted_interval_s=[float(times[0]), float(times[-1])],
        fitted_samples=len(times), requested_samples=len(time), usable_samples=int(usable.sum()),
        rms_phase_fit_residual_rad=float(np.sqrt(np.average(errors**2, weights=weights))),
        fitted_mode_cycles=float(angular_frequency * (times[-1] - times[0]) / (2 * np.pi)),
        max_adjacent_phase_step_rad=float(np.max(abs(np.diff(phase)))),
        median_mode_amplitude=float(np.median(amplitude[chosen])),
        median_spatial_residual=float(np.median(noise[chosen])),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diagnostics", help="NPZ with time_s, phi_rad and signal[time, probe]")
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--mode", type=int, required=True)
    parser.add_argument("--max-mode", type=int)
    parser.add_argument("--start-s", type=float)
    parser.add_argument("--end-s", type=float)
    parser.add_argument("--min-amplitude", type=float, default=0.)
    args = parser.parse_args()
    with np.load(args.diagnostics) as data:
        time = data["time_s"]
        interval = np.ones_like(time, dtype=bool)
        if args.start_s is not None:
            interval &= time >= args.start_s
        if args.end_s is not None:
            interval &= time <= args.end_s
        result = estimate(time[interval], data["phi_rad"], data["signal"][interval],
                          args.radius, args.mode, args.mode if args.max_mode is None else args.max_mode,
                          args.min_amplitude)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
