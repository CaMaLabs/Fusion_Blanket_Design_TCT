# Closed-loop TCT Trigger Validation Report

Status: `PASS_WITH_REDUCED_MODEL_BOUNDARIES`

## Already Completed Before This Run

- BOUT++ / M3D-C1 bridge artifacts:
  `validation_runs/m3dc1_bout_cross_validation_default/cross_validation_report.md`
  and `cross_validation_summary.json`.
- Resolved BOUT++ actuator robustness:
  `validation_runs/bout_tct_actuator_robustness_default/tct_actuator_robustness_summary.json`.
- BOUT++ validation ladder:
  `docs/bout_validation_plan.md`.
- M3D-C1-side proxy and integration artifacts:
  `/root/CaMaLabs_M3DC1/validation/generated/candidate0_physics_results.csv`,
  `/root/CaMaLabs_M3DC1/validation/real_c1_h5_report.md`, and
  `/root/CaMaLabs_M3DC1/validation/helical_benchmark_note.md`.

Existing timing boundary extracted from the actuator robustness run:

- nominal peak-current reduction: `0.141596`
- fine-grid peak-current reduction: `0.140518`
- delayed peak-current reduction: `0.000000`
- delayed2 integrated-current reduction: `0.548982`
- delayed4 integrated-current reduction: `0.448146`

M3D-C1 limitation preserved: The real public HEAT C1.h5 integration file fails reactor-relevant hard constraints; all five real-HDF5-derived cases failed with TBR<1.05 and Pnet<1.0. It is a real backend integration test, not reactor-relevant TCT validation.

## What This Run Adds

This run adds closed-loop reduced-MHD trigger validation using the existing
BOUT++ current-sheet actuator framework. Trigger policies include J-threshold,
dJ/dt-threshold, preemptive scheduled, delayed falsification, and no-control
baselines across base and fine grids, threshold variants, nominal and +20%
actuator strength, and latency cases.

It also writes an M3D-C1-compatible diagnostic contract at
`m3dc1_diagnostic_contract.json`. The contract is explicitly a diagnostic/control
contract and proxy bridge, not a real M3D-C1 run.

## Pass/Fail Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| nominal_and_fine_trigger_before_uncontrolled_peak | PASS | `{"base_margin": 1.0, "fine_margin": 1.0}` |
| nominal_closed_loop_reduces_post_initial_peak_J | PASS | `{"controlled": 0.3546998349488787, "reduction_fraction": 0.14159563381721751, "uncontrolled": 0.4132083303888408}` |
| nominal_closed_loop_reduces_integrated_max_J | PASS | `{"controlled": 2.4822798115879876, "reduction_fraction": 0.6533426292160718, "uncontrolled": 7.160614545637903}` |
| fine_grid_direction_matches_base_grid_direction | PASS | `{"base_integrated_reduction": 0.6533426292160718, "base_peak_reduction": 0.14159563381721751, "fine_integrated_reduction": 0.6507804641094235, "fine_peak_reduction": 0.14051812213292225}` |
| delayed_trigger_preserves_timing_falsification_boundary | PASS | `{"delayed_integrated_reduction": 0.49813038959519085, "delayed_peak_reduction": 0.0, "trigger_margin": -2.0}` |
| m3dc1_diagnostic_contract_valid_proxy_json | PASS | `{"artifact_type": "diagnostic_control_contract", "not_real_m3dc1_output": true}` |

## Strongest Result

`base_j_medium_plus20` gave the strongest integrated-current reduction:

- post-initial peak `|J|` reduction: `0.167591`
- time-integrated max `|J|` reduction: `0.699808`
- trigger time: `0.0`
- trigger margin before uncontrolled peak: `1.0`

## Weakest Result

`base_j_medium_latency1p5` is the weakest controlled case by peak-current reduction:

- post-initial peak `|J|` reduction: `0.000000`
- time-integrated max `|J|` reduction: `0.575870`
- trigger fired before current-sheet peak: `False`

This preserves the known falsification boundary: delayed/late triggering can
still reduce integrated current while failing the peak-current metric.

## Explicit Limitations

- This is closed-loop reduced-MHD trigger validation, not full tokamak-grade
  validation.
- The actuator is the existing reduced BOUT++ current-sheet model, not a measured
  liquid-metal actuator.
- The M3D-C1 bridge is an M3D-C1-compatible diagnostic contract, not a real
  M3D-C1 reactor output.
- The real public HEAT `C1.h5` file remains a backend integration test that
  fails reactor-relevant hard constraints.
- No experimental Mirnov, ECE, density, EFIT-evolution, or actuator telemetry was
  used in this run.

## Next Step

The next real validation step is to replace the reduced `J`/`dJ/dt` trigger
diagnostic with authorized M3D-C1 fields or experimental magnetic diagnostics,
then rerun the same contract so pre-peak trigger timing, actuator latency, and
peak/integrated-current metrics are measured against real diagnostic data.
