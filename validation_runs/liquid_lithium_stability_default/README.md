# Liquid Lithium Surface Stability Module

This validation layer is a deterministic reduced model for ranking
liquid-lithium surface-stability bench-test ideas. It is intentionally separate
from the BOUT++, M3D-C1, FreeGSNKE, FAIR-MAST, and Dedalus current-sheet
validation artifacts.

Run:

```bash
python scripts/run_liquid_lithium_stability.py \
  --run-dir validation_runs/liquid_lithium_stability_default
```

Outputs:

- `liquid_lithium_stability_results.csv`
- `liquid_lithium_stability_summary.json`
- `LIQUID_LITHIUM_STABILITY_REPORT.md`

Claim boundary: this module supports prioritizing capillary/porous
confinement, wetting microtexture, inert-gas/plasma boundary damping, and
magnetic damping for follow-up bench tests. It does not validate liquid lithium
surface stability in a reactor.
