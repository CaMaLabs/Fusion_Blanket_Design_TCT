# Biased Dedalus TCT Matrix Artifact Notes

## Purpose

This matrix is a reduced-MHD toy stress test for current-sheet diagnostics and
TCT-style proxy controls. It compares a finite-pulse driven island-onset
baseline against smoothing-only, biased wall-current-only, and combined
smoothing-plus-bias proxy cases.

## Strongest Result

The strongest case in this matrix is `smoothing_plus_bias_positive`.

- Baseline final island proxy count: `30`
- `smoothing_plus_bias_positive` final island proxy count: `7`
- Reduction versus baseline: `76.7%`

This means the combined smoothing and positive biased wall-current proxy reduced
the final island/plasmoid proxy burden in this toy setup.

## Diagnostic Definitions

- `final_island_count_proxy` is the final count of robust local maxima and
  minima of perturbation flux `psi - <psi>_x`.
- Candidate extrema are checked against the eight neighboring cells on the
  periodic grid using `island_o_point_prominence = 1e-5`.
- `time_to_secondary_island_proxy` is the first diagnostic time after `t=0` when
  the proxy reaches `max(onset_island_count_threshold, initial_count + 1)`.
- This is a morphology proxy, not a topological island count. It can count grid
  noise, miss weak/broad islands, double-count structures, and vary with
  threshold or resolution.
- `max_aspect_ratio` and `min_delta` use a half-maximum current-profile width.
  They can remain identical across cases when the coarse half-width diagnostic
  does not move even though island count, energy, or RMS current width changes.
- `current_weighted_delta_rms` and `current_weighted_aspect_ratio` provide a
  smoother current-profile width/aspect companion diagnostic, but they are still
  profile proxies rather than separatrix or topology measurements.

## Reproduction

```bash
cd /root/Fusion_Blanket_Design_TCT
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_matrix.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_matrix \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

## Caveats

- This is a reduced-model toy benchmark only.
- The island onset is driven by a finite artificial source pulse.
- The bias term is a prescribed reduced-MHD flux-source proxy.
- There is no tokamak geometry.
- There is no wall physics.
- There is no liquid lithium model.
- There are no electrodes, contact resistance, free-surface effects, sheath
  physics, or material response.
- This is not validation of TCT.

## Needed Next

- Parameter sweep over bias strength, polarity, mode number, and trigger timing.
- Resolution check at higher `nx`/`nz`.
- Independent diagnostic check for magnetic-island topology beyond local extrema.
- Physics review of whether the reduced source terms map to any credible
  actuator/current-closure mechanism.
