# Biased Dedalus TCT Numerical Falsification Study Notes

## Purpose

This artifact stress-tests the biased Dedalus reduced-MHD toy result against a
small set of numerical falsification checks:

- resolution change from `64x64` to `96x96`
- timestep reduction from `0.001` to `0.0005` at `64x64`
- local-extrema prominence sensitivity
- comparison of the original local-extrema island proxy against an independent
  connected-component morphology proxy

This remains a toy reduced-MHD numerical sanity artifact. It is not validation
of TCT, tokamak behavior, wall physics, liquid lithium, or a reactor concept.

## Reproduction

```bash
cd /root/Fusion_Blanket_Design_TCT
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_falsification_study.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_falsification_study \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

## Key Results

The combined smoothing-plus-bias cases retained positive reductions in both
proxy diagnostics across the compact grid:

| Case | Minimum island reduction | Minimum component reduction |
| --- | ---: | ---: |
| `smoothing_plus_bias_positive_0.0015` | `33.3%` | `50.0%` |
| `smoothing_plus_bias_negative_0.0020` | `46.4%` | `50.0%` |

The strongest single row was
`smoothing_plus_bias_positive_0.0015` at
`prominence_64_dt_0.001_prom_2e-5`:

- final island proxy: `3`
- final component proxy: `4`
- island reduction versus matched baseline: `89.3%`
- component reduction versus matched baseline: `66.7%`

## Weakest Result

`smoothing_only` did not pass the compact falsification screen:

- island reduction was not positive at `96x96`
- component reduction was negative at half timestep (`8 -> 10` components,
  `-25.0%`)

This makes smoothing-only a weaker reduced-model artifact than combined
smoothing-plus-bias in this specific toy setup.

## Caveats

- Reduced-MHD toy benchmark only.
- The island onset is driven by a finite artificial source pulse.
- Bias is a prescribed flux-source proxy.
- No tokamak geometry.
- No material wall model.
- No liquid lithium.
- No electrodes, contact resistance, sheath physics, free surfaces, or wall
  engineering.
- The island and component diagnostics are morphology proxies, not magnetic
  topology classifiers.
- The study is compact and not a full convergence campaign.
- The maximum energy-decay-fraction penalty for combined bias cases is about
  `0.0068`; that requires physics review before any stronger interpretation.

## What Remains Unvalidated

- Full resolution/timestep convergence.
- A topology-based island diagnostic using separatrix or O/X-point analysis.
- Sensitivity to domain size, resistivity, viscosity, drive amplitude, drive
  duration, and source shape.
- Any mapping from the prescribed source term to a physical actuator.
- Agreement with BOUT++, M3D-C1, JOREK, or experimental diagnostics.
