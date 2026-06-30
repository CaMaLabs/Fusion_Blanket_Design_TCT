# Dedalus Current-Sheet Toy Benchmark

This directory contains a minimal Dedalus benchmark for a 2D reduced/resistive
MHD current-sheet problem. It is intended to test whether current-sheet
half-thickness, sheet aspect ratio, reconnection-rate proxies, and island onset
metrics provide useful diagnostic information in a reduced reconnection problem.

This is only a reduced-MHD toy benchmark. It is not validation of TCT, not a
tokamak calculation, not M3D-C1 output, not kinetic/PIC physics, and not a
reactor claim.

## Model

The benchmark evolves 2D reduced MHD in a periodic Cartesian box:

```text
dt(psi) - eta Delp2(psi) = -[phi, psi] + control
dt(omega) - nu Delp2(omega) = -[phi, omega] + [psi, J]
Delp2(phi) + tau_phi + omega = 0
integ(phi) = 0
J = -Delp2(psi)
[a, b] = dx(a) dz(b) - dz(a) dx(b)
```

The in-plane magnetic field is `B = zhat x grad(psi)`. The initial condition is
a periodic double-Harris current sheet with a small flux perturbation. A double
sheet is used so the first version can keep periodic Fourier bases in both
directions. The scalar `tau_phi` and `integ(phi)=0` gauge condition remove the
singular mean mode from the periodic Poisson solve for `phi`.

## Runs

The runner executes two cases by default:

- `baseline`: no control term.
- `tct_style_perturbed`: same initial condition, but a transparent localized
  smoothing term is activated when the measured sheet aspect ratio `L/delta`
  crosses `control_aspect_threshold`.

The control term is intentionally simple and easy to disable:

```text
control = control_strength * Delp2(psi) * exp(-((z - z_sheet)/control_width)^2)
```

This should be interpreted only as a TCT-style proxy perturbation for diagnostic
testing. It is not a physical liquid-lithium actuator model.

## Outputs

Each case writes:

- `diagnostics.csv`
- `summary.json`
- `snapshots.npz`

The top-level run directory writes:

- `benchmark_summary.json`
- `diagnostics_summary.json` after plotting
- `plots/*.png` after plotting

## Diagnostics

The runner computes:

- current-sheet half-thickness `delta`
- sheet length `L`
- aspect ratio `L/delta`
- max `|J|`
- `J` p99
- reconnection-rate proxy `eta max(|J|)` at the active sheet
- magnetic energy
- island/plasmoid proxy count
- time-to-onset of secondary islands, based on the island proxy crossing a
  configurable count threshold

The island count is a deliberately cheap local-extrema proxy on `psi`; it is a
screening diagnostic, not a rigorous magnetic-island topology classifier.

## Example

Install Dedalus in the active Python environment first. Dedalus can be sensitive
to MPI and BLAS/threading configuration; for small local runs use one process and
disable extra threading:

```bash
export OMP_NUM_THREADS=1
cd /root/Fusion_Blanket_Design_TCT
python3 validation_models/dedalus_current_sheet/dedalus_current_sheet_benchmark.py \
  --run-dir validation_runs/dedalus_current_sheet_default \
  --nx 192 --nz 192 \
  --stop-time 3.0

python3 validation_models/dedalus_current_sheet/plot_dedalus_current_sheet_diagnostics.py \
  --run-dir validation_runs/dedalus_current_sheet_default
```

For a faster smoke test:

```bash
python3 validation_models/dedalus_current_sheet/dedalus_current_sheet_benchmark.py \
  --run-dir validation_runs/dedalus_current_sheet_smoke \
  --nx 64 --nz 64 \
  --stop-time 0.2 \
  --diagnostic-cadence 5 \
  --snapshot-cadence 20
```

## Limitations

- Periodic double-Harris geometry is a convenience, not tokamak geometry.
- The model is reduced/resistive MHD only.
- There are no particles, no PIC effects, no kinetic closures, no sheath
  physics, and no experimental diagnostics.
- The control term is a diagnostic perturbation, not a validated actuator.
- The plasmoid/island metric is a proxy based on local extrema, not a full
  magnetic-topology analysis.

Use this benchmark to test diagnostic ideas and control-trigger sensitivity
before attempting higher-fidelity BOUT++, M3D-C1, JOREK, or experimental-data
validation.
