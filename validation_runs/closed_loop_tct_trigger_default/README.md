# Closed-loop TCT Trigger Validation

Status: `PASS_WITH_REDUCED_MODEL_BOUNDARIES`

This directory contains a closed-loop reduced-MHD trigger validation pass and an
M3D-C1-compatible diagnostic contract. It is reduced-model evidence, not full
tokamak-grade validation and not a real M3D-C1 reactor output.

Files:

- `closed_loop_trigger_results.csv`
- `closed_loop_trigger_summary.json`
- `closed_loop_trigger_report.md`
- `m3dc1_diagnostic_contract.json`

The run preserves the known timing boundary: late/delayed actuation can reduce
time-integrated max `|J|` while failing to reduce post-initial peak `|J|`.
