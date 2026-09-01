# TCT Control Architecture V2C

V2C is a frozen reconciliation rung, not a larger evolutionary search.

It corrects two V2B limitations:

1. Each impulse, sustained, and full stage now receives a separately executed
   zero-actuation reference with the exact same `ntimemax` and output cadence.
2. Sustained/full scoring covers the complete equal-physical-time trajectory,
   including post-command decay and sheet reformation.

Sustained control additionally requires positive integrated width response,
at least 60% positive-width samples, and no peak-J excursion above 0.5%.
Impulse authority remains a separate peak-response gate.

The frozen seeds ablate momentum at identical magnetic settings for both the
known `-0.01` pulse and the strongest V2B magnetic geometry. This determines
whether the hybrid label represents real momentum synergy or magnetic response
alone. No physics coefficients are mutable.

Run:

```bash
cd tools/tct_mechanism_explorer
bash run_control_v2c.sh
```

Results are written under:

```text
validation_runs/tct_control_architecture_v2c/
```
