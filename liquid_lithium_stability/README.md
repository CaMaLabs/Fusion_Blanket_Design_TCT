# Liquid Lithium Surface Stability

This module contains the lightweight reduced-model layer for liquid-lithium
surface-stability prioritization.

Main entry point:

```bash
python scripts/run_liquid_lithium_stability.py \
  --run-dir validation_runs/liquid_lithium_stability_default \
  --check
```

Primary outputs:

- `validation_runs/liquid_lithium_stability_default/liquid_lithium_stability_results.csv`
- `validation_runs/liquid_lithium_stability_default/liquid_lithium_stability_summary.json`
- `validation_runs/liquid_lithium_stability_default/LIQUID_LITHIUM_STABILITY_REPORT.md`

Literature synthesis:

- `LIQUID_LITHIUM_STABILIZATION_LITERATURE.md`

Claim boundary:

This is a deterministic reduced-model scenario matrix. It is not reactor
validation, not free-surface MHD, not liquid-lithium material compatibility
validation, and not proof that TCT or lithium-current coupling works.
