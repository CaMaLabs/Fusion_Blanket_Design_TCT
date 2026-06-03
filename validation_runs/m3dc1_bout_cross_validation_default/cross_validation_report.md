# M3D-C1 / BOUT++ Cross-Validation Status

Generated: `2026-06-03T00:52:13.532303+00:00`

Overall status: **PASS_WITH_REDUCED_MODEL_BOUNDARIES**

## Gate Summary

| Gate | Status | Evidence |
| --- | --- | --- |
| `m3dc1_helical_proxy_hdf5_schema` | pass | `{"field_count": 23, "helical_proxy_flag": 1, "missing_required_fields": []}` |
| `m3dc1_candidate_proxy_constraints` | pass | `{"best_case": "aggressive_tct", "min_TBR": 1.1008, "rows": 5}` |
| `open_source_equilibrium_verifier` | pass | `{"returncode": 0, "stdout": "...                                                                      [100%]\n3 passed in 34.11s\n"}` |
| `bout_preemptive_actuator_supported` | pass | `{"nominal_integrated_reduction": 0.6533426292161446, "nominal_peak_reduction": 0.14159563381722218}` |
| `bout_fine_grid_direction_preserved` | pass | `{"fine_integrated_reduction": 0.650780464112708, "fine_peak_reduction": 0.14051812213299775}` |
| `timing_boundary_detected` | pass | `{"timing_min_integrated_reduction": 0.44814560157366523, "timing_min_peak_reduction": 0.0}` |

## Interpretation

The combined evidence supports TCT as a preemptive edge/current-sheet conditioning concept in reduced plasma-side checks.
It does not yet establish full tokamak-grade validation because the M3D-C1 helical artifact is a source-inspired proxy and the BOUT++ actuator is a reduced-MHD slab model.
The falsification boundary is explicit: delayed actuation still lowers integrated current but does not prevent peak current after the sheet has formed.

## Next Step

Build a closed-loop trigger that turns on the resolved actuator before the current-sheet peak, then export the same trigger schedule as an M3D-C1-compatible backend diagnostic contract.

Passed gates: `6/6`
