# Native M3D-C1 Magnetic Pulse-Train Audit

This is the next rung after the high-resolution impulse map classified the fixed `A=-0.01` magnetic pulse as transiently broadening but reversing shortly afterward.

## Frozen test

The audit does **not** tune amplitude. It keeps:

- `mag_ctrl_amp = -0.01`
- `dt = 0.01`
- `ramp = 0`
- same magnetic source center/width used by the prior native magnetic-operator studies
- same GEM baseline, mesh, and solver family

It varies only pulse timing/duty cycle:

| case | period | on-time | duty |
|---|---:|---:|---:|
| `single_reference` | single pulse | 0.05 | n/a |
| `train_p040_w020` | 0.04 | 0.02 | 50% |
| `train_p050_w020` | 0.05 | 0.02 | 40% |
| `train_p060_w020` | 0.06 | 0.02 | 33.3% |
| `train_p050_w030` | 0.05 | 0.03 | 60% |

The pulse train is active from `t=0` through `t=0.35`, while the matched runs continue through `t=0.40`.

## Native operator extension

`pulse_train_audit.py install` makes a minimal, default-neutral extension to the already-present local `imag_control` source in `/home/ubuntu/M3DC1-official`:

- `mag_ctrl_period`
- `mag_ctrl_pulse_width`

Defaults are zero, which preserves the prior single-gate behavior. The patch only changes the time gate around the existing localized magnetic flux/vector-potential source; it does not change resistivity, viscosity, GEM `eps`, equilibrium, mesh, or solver physics.

## Pass gate

A pulse train is only classified as sustained control when both are true over the active window:

1. sheet width remains positively shifted for most samples and has positive mean gain;
2. integrated high-|J| loading decreases without peak `Jpk` exceeding the predeclared worsening tolerance.

Width-only broadening does not count as full control.

## Run

From the repo root:

```bash
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
export TMPDIR=/var/tmp
bash tools/tct_mechanism_explorer/run_pulse_train_audit.sh
```

Large M3D-C1 HDF5 trees are written under:

```text
/tmp/m3dc1_tct_magnetic_pulse_train_runs
```

Compact evidence is written under:

```text
validation_runs/m3dc1_tct_magnetic_pulse_train/
```

Primary outputs:

- `pulse_train_plan.json`
- `zero_equivalence.json`
- `pulse_train_matrix.csv`
- `pulse_train_summary.json`
- `M3DC1_MAGNETIC_PULSE_TRAIN_REPORT.md`
- per-case compact `C1input`, `C1ke`, status, and delta CSVs
- `m3dc1_pulse_train_source.diff`
- runtime provenance

## Claim boundary

This is a native normalized GEM control study. A positive result would show that a repeated magnetic waveform can maintain a favorable current-sheet/current-loading response in the tested M3D-C1 case. It does not by itself validate liquid-lithium dimensional transfer, reactor stabilization, ELM suppression, or experimental TCT performance.
