# M3D-C1 / BOUT++ / GEQDSK Validation Summary

This is the reviewer-facing summary of the current plasma-side validation chain for Reference Design V1.

## Current status

```text
PASS_WITH_REDUCED_MODEL_BOUNDARIES
```

This means the repository has meaningful M3D-C1/BOUT++/GEQDSK validation artifacts, but not full tokamak-grade experimental validation.

## Evidence chain

```text
Reference Design V1
  -> be_outer_kill / be_outer_killer blanket basin
  -> BOUT++ conduction / blob / turbulence / current-sheet checks
  -> BOUT++ resolved actuator robustness sweep
  -> M3D-C1 Candidate-0 proxy campaign
  -> M3D-C1 / BOUT++ cross-validation bridge
  -> DIII-D GEQDSK / EFIT baseline, smoke, pass, convergence, and probe artifacts
```

## What is already completed

### BOUT++ reduced-model validation

Completed BOUT++ rungs include:

1. conduction sanity check,
2. controlled sweep,
3. robustness sweep,
4. blob / SOL source-shaping check,
5. Hasegawa-Wakatani reduced turbulence check,
6. resolved reduced-MHD current-sheet check,
7. resolved actuator robustness check.

Strongest BOUT++ result so far:

- `14` controlled actuator cases tested.
- `12` reduced both post-initial peak current and time-integrated max current.
- all `14` reduced time-integrated max current.
- nominal base actuator reduced post-initial peak current by about `14.16%`.
- nominal base actuator reduced integrated max current by about `65.33%`.
- fine-grid nominal actuator preserved the direction.
- delayed/pulsed timing remains the main falsification boundary.

Primary artifacts:

```text
docs/bout_validation_plan.md
bout_validation_bridge.py
bout_controlled_sweep.py
bout_robustness_sweep.py
bout_blob_sol_sweep.py
bout_hw_turbulence_sweep.py
bout_tct_current_sheet_sweep.py
bout_tct_actuator_robustness_sweep.py
validation_models/tct_current_sheet/
validation_runs/bout_tct_actuator_robustness_default/tct_actuator_robustness_summary.json
```

Interpretation:

> BOUT++ supports a reduced-model version of preemptive edge/current-sheet conditioning. It does not prove full reactor-scale TCT control.

### M3D-C1 Candidate-0 proxy campaign

Candidate-0 is wired as the M3D-C1-facing validation target for the current reference basin.

Candidate-0 includes:

```text
blanket_topology = be_outer_killer
active_tct = true
liquid_lithium_wall = true
TCT translation mode = current_profile_broadening_proxy
```

The Candidate-0 matrix includes:

```text
baseline                  tct_strength = 0.0   li_current = 0.0
weak_tct                  tct_strength = 0.2   li_current = 0.0
moderate_tct              tct_strength = 0.5   li_current = 0.05
aggressive_tct            tct_strength = 0.8   li_current = 0.0
aggressive_tct_li_current tct_strength = 0.8   li_current = 0.1
```

Interpretation:

> The lithium-current variant exists and is carried through the M3D-C1-facing proxy path. Current evidence supports keeping it as a retained hypothesis, not claiming a separately proven independent effect.

Primary artifacts in `CaMaLabs/M3DC1`:

```text
validation/generated/candidate0_cases.csv
validation/generated/candidate0_physics_results.csv
validation/generated/candidate0_case_matrix.json
validation/helical_benchmark_note.md
validation/results/*/validation_results.csv
```

### M3D-C1 / BOUT++ cross-validation bridge

The cross-validation bridge combines M3D-C1 proxy artifacts, FreeGSNKE equilibrium checks, and the BOUT++ actuator robustness result.

The completed bridge reports:

```text
Overall status: PASS_WITH_REDUCED_MODEL_BOUNDARIES
Passed gates: 6/6
```

Passed gates:

1. `m3dc1_helical_proxy_hdf5_schema`
2. `m3dc1_candidate_proxy_constraints`
3. `open_source_equilibrium_verifier`
4. `bout_preemptive_actuator_supported`
5. `bout_fine_grid_direction_preserved`
6. `timing_boundary_detected`

Primary artifacts:

```text
m3dc1_bout_cross_validation.py
validation_runs/m3dc1_bout_cross_validation_default/cross_validation_report.md
validation_runs/m3dc1_bout_cross_validation_default/cross_validation_summary.json
```

Interpretation:

> The bridge supports the validation workflow and reduced-model consistency. It does not claim full M3D-C1 validation of the reactor.

### Real public `C1.h5` integration test

A real public M3D-C1-style `C1.h5` file from the HEAT repository was found and processed.

Result:

- the real file was useful as a backend integration test,
- but it failed current reactor-relevant hard gates due to low `TBR` and `Pnet`,
- so it should not be treated as a reactor-relevant validation success.

Primary artifact in `CaMaLabs/M3DC1`:

```text
validation/real_c1_h5_report.md
```

Interpretation:

> The real `C1.h5` test proves the extractor/integration path can touch a public real file. It does not validate Reference Design V1.

### DIII-D GEQDSK / EFIT chain

Recent repository history now includes a DIII-D GEQDSK/EFIT validation chain.

Relevant commit sequence includes:

```text
Add DIII-D GEQDSK EFIT baseline case
Document GEQDSK baseline provenance
Add M3D-C1 GEQDSK smoke run
Add M3D-C1 GEQDSK smoke pass artifacts
Add DIII-D mesh convergence and GEQDSK consistency
Add M3DC1 GEQDSK probe artifacts
```

Current interpretation:

> The project now has a DIII-D EFIT/GEQDSK anchor and M3D-C1-facing probe/smoke/convergence artifacts. This closes the earlier criticism that there was no GEQDSK/EFIT baseline at all. It still does not mean the full reactor design has been experimentally validated.

## Conservative claim boundary

Defensible:

> Reference Design V1 now has a coherent plasma-side validation chain: BOUT++ reduced-model actuator evidence, M3D-C1 proxy/candidate handoff, real `C1.h5` integration testing, and DIII-D GEQDSK/EFIT anchoring.

Not defensible yet:

> Reference Design V1 has been fully validated by M3D-C1, experimentally validated, or proven as a reactor design.

## Main remaining gap

The next highest-value validation step is:

```text
closed-loop trigger-aware reduced-MHD validation
  -> trigger fires before current-sheet peak
  -> actuator reduces peak and integrated current
  -> timing failure boundary remains explicit
  -> M3D-C1-compatible diagnostic/control contract is exported
```

This is the natural follow-up because the existing BOUT++ results show timing is the hard boundary: preemptive actuation helps; delayed actuation can miss the peak-current metric.

## Current standing

The project is no longer just a concept repository.

It is now best described as:

> An open-source fusion design and validation pipeline with a frozen Reference Design V1, an OpenMC-selected blanket basin, BOUT++ reduced-MHD actuator evidence, M3D-C1 proxy/candidate artifacts, and a DIII-D GEQDSK/EFIT validation anchor.
