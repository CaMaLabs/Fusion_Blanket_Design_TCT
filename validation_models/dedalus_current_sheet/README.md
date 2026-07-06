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

Additional segmented source modes are available for actuator-shape
falsification:

- `rib_matrix`: tanh-smoothed toroidal rib-like source bands.
- `smooth_rib_matrix`: sinusoidal rib-like source envelope with reduced sharp
  transitions.
- `mesh`: rib-like source bands with an additional cross modulation.
- `smooth_mesh`: crossed sinusoidal mesh-like source envelope.
- `channelized`: low-spatial-frequency channel-like source intended to mimic
  geometrically constrained flow/source paths.
- `capillary_stabilized`: smooth standing source with high-spatial-frequency
  attenuation and a capillary-damping risk proxy.
- `magnetic_stiffened`: smooth standing source attenuated by a magnetic
  pressure/stiffening proxy.
- `phase_locked_rib`: rib-like source bands shifted by `bias_phase`.

These modes are prescribed source-shape proxies only. They do not model
electrodes, insulators, sheaths, contact resistance, arcing, material response,
or `J x B` structural loading.

The benchmark also records source-sharpness proxies for biased runs:

- `bias_source_gradient_rms`: RMS gradient of the prescribed bias source.
- `bias_source_laplacian_rms`: RMS laplacian of the prescribed bias source.
- `surface_displacement_risk_proxy`: a scalar source-risk proxy based on source
  gradient plus laplacian, attenuated by the configured capillary,
  magnetic-stiffening, and channel-count proxy factors.

These are not free-surface MHD quantities. They are only cheap diagnostics for
whether a prescribed source is spatially sharp enough that it should be treated
as a higher surface-disturbance risk in the toy model.

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
- RMS current-profile width `current_weighted_delta_rms`
- RMS-width aspect ratio `current_weighted_aspect_ratio`
- max `|J|`
- `J` p99
- reconnection-rate proxy `eta max(|J|)` at the active sheet
- magnetic energy
- island/plasmoid proxy count
- connected-component morphology proxy count
- time-to-onset of secondary islands, based on the island proxy crossing a
  configurable count threshold

The island count is a deliberately cheap local-extrema proxy on the perturbation
flux; it is a screening diagnostic, not a rigorous magnetic-island topology
classifier.

Implementation details:

- `final_island_count_proxy` is the final count of robust local maxima and
  minima of the perturbation flux `psi - <psi>_x`. The x-averaged Harris-sheet
  equilibrium is subtracted before extrema are counted, so the proxy responds to
  island-like perturbation structure rather than the background sheet.
- Candidate O-point proxies are detected on the periodic grid by comparing each
  cell to its eight neighbors. A local maximum must exceed all neighbors by
  `island_o_point_prominence`; a local minimum must be lower than all neighbors
  by the same prominence.
- `time_to_secondary_island_proxy` is the first diagnostic time after `t=0` when
  the island proxy reaches `max(onset_island_count_threshold,
  initial_island_count_proxy + 1)`.
- `delta` is estimated from the half-maximum current-sheet width in `z`.
- `L` is estimated as the active `x` extent where sheet current exceeds half of
  the local sheet peak.
- `current_weighted_delta_rms` is a smoother RMS width of the x-averaged `|J|`
  profile around each of the two strongest current-sheet peaks. A +/- `nz/4`
  window prevents the two periodic sheets from being mixed.
- `current_weighted_aspect_ratio` is `L/current_weighted_delta_rms`.
- `component_count_proxy` is an independent morphology proxy. It thresholds the
  positive and negative lobes of perturbation flux `psi - <psi>_x` and counts
  periodic 4-connected components with at least `component_min_cells`. The
  threshold is `max(component_threshold_fraction * max(abs(psi_perturb)),
  5 * island_o_point_prominence)`.
- `max_aspect_ratio` and `min_delta` can remain identical across matrix cases
  when the proxy changes island content or magnetic energy without changing the
  half-maximum sheet-width diagnostic on this coarse grid. In that situation the
  island proxy, current/energy metrics, and RMS-width diagnostic are more
  sensitive than the simple half-width metric.

Island proxy failure modes:

- It is not a topological magnetic-island count and does not trace separatrices.
- It does not robustly distinguish all O-points from X-points.
- It can count grid noise if `island_o_point_prominence` is too small.
- It can miss broad or weak islands if the prominence threshold is too large.
- It can double-count one physical island if multiple extrema sit inside the
  same island-like structure.
- It can be resolution and cadence sensitive.

Component proxy failure modes:

- It is also not a topological island count.
- It can merge nearby structures into one component.
- It can split one broad structure if the contour is noisy.
- It depends on the threshold fraction and minimum cell count.
- It can disagree with the local-extrema proxy; such disagreement should be
  treated as a warning, not averaged away.

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

For the compact parameter sweep:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_parameter_sweep.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_parameter_sweep \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

This sweep includes one unbiased baseline reference plus the requested 16-case
grid:

- `bias_strength`: `0.0005`, `0.0010`, `0.0015`, `0.0020`
- `bias_polarity`: `+1`, `-1`
- `control_enabled`: `false`, `true`

Reductions are computed relative to `reference_unbiased_baseline`.

For the first resolution sanity check:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_resolution_check.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_resolution_check \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

The resolution check compares `baseline`, `smoothing_only`, and
`smoothing_plus_bias_positive` at `64x64` and `96x96`. Reductions are computed
relative to the baseline at the same resolution. Passing this check only means
the direction of the island-proxy reduction persists qualitatively across this
small grid change.

For the compact numerical falsification study:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_falsification_study.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_falsification_study \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

This study compares `baseline`, `smoothing_only`,
`smoothing_plus_bias_positive_0.0015`, and
`smoothing_plus_bias_negative_0.0020` across a compact grid:

- `64x64` and `96x96` at nominal timestep and prominence.
- `64x64` at half timestep.
- `64x64` across local-extrema prominence `5e-6`, `1e-5`, and `2e-5`.

The intended falsification readout is strict: a candidate is more credible only
if both island and component morphology proxies improve versus the matched
condition baseline, and if resolution/timestep changes do not flip the result.

For the segmented rib/mesh actuator-shape matrix:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_segmented_bias_actuator_matrix.py \
  --run-dir validation_runs/dedalus_segmented_bias_actuator_matrix_default \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

The first segmented matrix is a negative/diagnostic result for sharp rib
forcing: smooth standing bias remains strongest, while sharp rib variants
increase island and component morphology proxies. Mesh-like forcing is less
harmful but weaker than smooth standing bias in this toy setup.

For the non-acoustic surface-stabilized bias matrix:

```bash
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_surface_stabilized_bias_matrix.py \
  --run-dir validation_runs/dedalus_surface_stabilized_bias_matrix_default \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

This matrix tests every current surface-stabilization proxy except acoustics:

| `surface_case` | Meaning |
| --- | --- |
| `baseline` | Driven island-onset stress test without smoothing or bias. |
| `smooth_standing_bias_positive` | Smooth standing bias source; source-risk reference. |
| `smooth_rib_bias_positive` | Smoothed rib envelope instead of sharp segmented ribs. |
| `smooth_mesh_bias_positive` | Smoothed crossed mesh-like source envelope. |
| `capillary_stabilized_bias` | Standing source with capillary damping and high-frequency source attenuation proxies. |
| `magnetic_stiffened_bias` | Standing source attenuated by magnetic pressure/stiffening proxy. |
| `channelized_bias` | Low-frequency source divided across nominal channels. |
| `prebiased_smooth_pulse` | Smooth source applied as a finite smooth pulse. |
| `smoothing_only` | Aspect-triggered localized smoothing proxy only. |
| `smoothing_plus_capillary_stabilized` | Localized smoothing plus capillary-stabilized source proxy. |
| `smoothing_plus_magnetic_stiffened` | Localized smoothing plus magnetic-stiffening source proxy. |
| `smoothing_plus_channelized` | Localized smoothing plus channelized source proxy. |
| `smoothing_plus_smooth_rib` | Localized smoothing plus smoothed rib source envelope. |
| `smoothing_plus_prebiased_smooth_pulse` | Localized smoothing plus finite smooth pulse bias source. |

The surface-stabilized matrix is still a prescribed-source reduced-MHD toy
study. It does not model acoustic damping, active wave cancellation,
capillary-wave dynamics, wall wetting, lithium flow, liquid-metal MHD,
electrodes, or real Lorentz-force loading.

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
- Segmented rib/mesh modes are source-shape tests only. They do not validate or
  invalidate real electrode-rib hardware.
- Surface-stabilized source modes are source-shaping and source-risk proxies
  only. They are not capillary, channel-flow, magnetic-pressure, or pulse-power
  engineering models.
- The plasmoid/island metric is a proxy based on local extrema, not a full
  magnetic-topology analysis.

Use this benchmark to test diagnostic ideas and control-trigger sensitivity
before attempting higher-fidelity BOUT++, M3D-C1, JOREK, or experimental-data
validation.
