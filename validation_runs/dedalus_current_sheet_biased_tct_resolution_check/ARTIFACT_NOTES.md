# Biased Dedalus TCT Resolution Check Notes

## Purpose

This is a first numerical sanity check for the biased Dedalus toy matrix. It
compares baseline, smoothing-only, and smoothing-plus-positive-bias cases at
`64x64` and `96x96`.

## Reproduction

```bash
cd /root/Fusion_Blanket_Design_TCT
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_resolution_check.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_resolution_check \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

## Result Summary

| Resolution | Baseline final island proxy | Smoothing-only | Smoothing + positive bias | Reduction vs same-resolution baseline |
| --- | ---: | ---: | ---: | ---: |
| `64x64` | `30` | `20` | `7` | `76.7%` |
| `96x96` | `24` | `24` | `16` | `33.3%` |

The combined smoothing-plus-positive-bias case retains the same qualitative
direction at `96x96`, but the magnitude weakens substantially. This is a useful
caution: the matrix result is not resolution-converged.

## Caveats

- Reduced-MHD toy benchmark only.
- Prescribed source term only.
- No tokamak geometry.
- No material wall model.
- No liquid lithium.
- No TCT validation claim.
- Two resolutions are not a convergence study.

## What Remains Unvalidated

- A broader grid and timestep convergence study.
- A topology-based island diagnostic.
- Independent review of the forcing/source formulation.
- Comparison against a higher-fidelity open MHD code or experimental diagnostic
  dataset.
