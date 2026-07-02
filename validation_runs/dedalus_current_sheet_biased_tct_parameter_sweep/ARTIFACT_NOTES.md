# Biased Dedalus TCT Parameter Sweep Notes

## Purpose

This sweep is a compact reduced-MHD toy stress test for sensitivity to prescribed
biased flux-source strength, polarity, and the presence/absence of the smoothing
control proxy. It is not a tokamak, wall, liquid-lithium, or TCT validation run.

## Reproduction

```bash
cd /root/Fusion_Blanket_Design_TCT
. .venv-dedalus/bin/activate
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/mpich/lib:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}
export UCX_TLS=self
export OMP_NUM_THREADS=1
python validation_models/dedalus_current_sheet/run_biased_tct_parameter_sweep.py \
  --run-dir validation_runs/dedalus_current_sheet_biased_tct_parameter_sweep \
  --python /root/Fusion_Blanket_Design_TCT/.venv-dedalus/bin/python
```

## Result Summary

- Reference unbiased baseline final island proxy: `30`
- Best controlled case by final island proxy: `control_bias_negative_0.0020`
- Best controlled final island proxy: `5`
- Best controlled reduction versus reference baseline: `83.3%`

The result is polarity/strength sensitive and should be treated as a numerical
screening result only. It motivates review of the source term and diagnostics; it
does not establish a physical actuator.

## Caveats

- Reduced-MHD toy benchmark only.
- Island onset is driven by a finite artificial source pulse.
- Bias is a prescribed reduced-MHD flux source.
- No tokamak geometry.
- No material wall model.
- No liquid lithium.
- No electrodes, contact resistance, sheath physics, free surface, or wall
  engineering.
- No TCT validation claim.

## What Remains Unvalidated

- Whether the local-extrema island proxy agrees with a topology-based island
  diagnostic.
- Whether results persist under broader resolution, timestep, and threshold
  sweeps.
- Whether the prescribed source term has a defensible mapping to any physical
  current-closure mechanism.
- Whether any similar behavior appears in BOUT++, M3D-C1, JOREK, or experimental
  diagnostic data.
