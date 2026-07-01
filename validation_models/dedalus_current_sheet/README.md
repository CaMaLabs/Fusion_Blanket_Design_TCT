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

An optional onset driver can be enabled with `--drive-enabled`. This applies the
same small, multimode flux source to both baseline and perturbed cases over a
finite time window:

```text
drive_start_time <= t <= drive_end_time
```

Use this only as a driven-onset stress test. It is not spontaneous plasmoid
formation from the unforced sheet.

The control term is intentionally simple and easy to disable:

```text
control = control_strength * Delp2(psi) * exp(-((z - z_sheet)/control_width)^2)
```

This should be interpreted only as a TCT-style proxy perturbation for diagnostic
testing. It is not a physical liquid-lithium actuator model.

The benchmark also supports a biased wall-current proxy:

```text
bias = bias_polarity * bias_strength * wall_current_shape(x, z)
```

This is a prescribed reduced-MHD flux source near the two current-sheet/wall
proxy layers. It can be run as a standing bias or an aspect-ratio-triggered
bias. It is only meant to test whether a current-through-wall-style reduced
proxy changes island count, peak current, or reconnection diagnostics. It is not
liquid-lithium MHD, not an electrode/contact model, and not wall engineering.

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

Implementation details:

- `final_island_count_proxy` is the final count of robust local maxima and
  minima of the perturbation flux `psi - <psi>_x`. The x-averaged Harris-sheet
  equilibrium is subtracted before extrema are counted, so the proxy responds to
  island-like perturbation structure rather than the background sheet.
- `time_to_secondary_island_proxy` is the first diagnostic time after `t=0` when
  the island proxy reaches `max(onset_island_count_threshold,
  initial_island_count_proxy + 1)`.
- `delta` is estimated from the half-maximum current-sheet width in `z`.
- `L` is estimated as the active `x` extent where sheet current exceeds half of
  the local sheet peak.
- `max_aspect_ratio` and `min_delta` can remain identical across matrix cases
  when the proxy changes island content or magnetic energy without changing the
  half-maximum sheet-width diagnostic on this coarse grid. In that situation the
  island proxy and current/energy metrics are more sensitive than the simple
  width metric.

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

For a finite-pulse island-onset stress test:

```bash
python3 validation_models/dedalus_current_sheet/dedalus_current_sheet_benchmark.py \
  --run-dir validation_runs/dedalus_current_sheet_driven_pulse_compare \
  --case both \
  --nx 64 --nz 64 \
  --eta 2e-4 --nu 2e-4 \
  --delta0 0.16 \
  --perturbation-amplitude 0.001 \
  --drive-enabled \
  --drive-start-time 0.5 \
  --drive-end-time 0.7 \
  --drive-strength 0.002 \
  --drive-kx 4 \
  --control-aspect-threshold 80 \
  --stop-time 2.0
```

For a compact biased TCT matrix:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_matrix.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_matrix \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

The matrix compares baseline, smoothing-only, positive/negative bias-only, and
smoothing-plus-bias cases. The polarity comparison is a falsification check: a
biased mode that only helps for one sign should be treated as sign-sensitive
reduced-model behavior, not general validation.

Matrix cases:

| `matrix_case` | Meaning |
| --- | --- |
| `baseline` | Finite-pulse driven island-onset stress test with no TCT proxy. |
| `smoothing_only` | Aspect-triggered localized smoothing proxy only. |
| `bias_positive_standing` | Standing positive biased wall-current proxy only. |
| `bias_negative_standing` | Standing negative biased wall-current proxy only. |
| `smoothing_plus_bias_positive` | Smoothing proxy plus positive biased wall-current proxy. |
| `smoothing_plus_bias_negative` | Smoothing proxy plus negative biased wall-current proxy. |

The output also includes `benchmark_case`, which records the underlying
single-case benchmark directory name: `baseline` or `tct_style_perturbed`.

## Limitations

- Periodic double-Harris geometry is a convenience, not tokamak geometry.
- The model is reduced/resistive MHD only.
- There are no particles, no PIC effects, no kinetic closures, no sheath
  physics, and no experimental diagnostics.
- The control term is a diagnostic perturbation, not a validated actuator.
- The optional drive term is artificial. It can test whether diagnostics respond
  when island-like structures are forced to appear, but it is not natural
  plasmoid onset.
- The biased wall-current proxy is a prescribed flux source. It does not model
  liquid-lithium flow, free surfaces, electrodes, contact resistance, sheath
  physics, or wall engineering.
- The plasmoid/island metric is a proxy based on local extrema, not a full
  magnetic-topology analysis.

Use this benchmark to test diagnostic ideas and control-trigger sensitivity
before attempting higher-fidelity BOUT++, M3D-C1, JOREK, or experimental-data
validation.
