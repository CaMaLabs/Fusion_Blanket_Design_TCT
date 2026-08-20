# Validation Status

This file gives a single-page status view for reviewers.

Nothing in this repository should be interpreted as a demonstrated reactor design. The current value of the repository is the validation pipeline, assumptions registry, candidate-generation code, validation scaffolding, and provenance-preserving development history.

## Status legend

| Status | Meaning |
|---|---|
| Implemented | Present in repository code, documents, or committed artifacts. |
| Smoke-tested | Basic syntax / lightweight CI or startup path exists. |
| Screening-level | Useful for candidate generation, not final validation. |
| Preliminary support | Early result or scaffold exists, but not enough for a strong physics claim. |
| Needs benchmark | Requires a small accepted test case before technical claims are strong. |
| Needs expert review | Requires review by a domain expert or supported code user. |
| Not validated | Should not be used as evidence yet. |
| Provenance only | Retained to preserve development history; not a current recommended code path. |

## Current validation matrix

| Component | Current status | Evidence in repo | Next validation step |
|---|---|---|---|
| Repository review structure | Implemented | `README.md`, `ROADMAP.md`, `FUNDING.md`, `ARCHIVE_INDEX.md`, `docs/assumptions.md`, `docs/falsification_tests.md`, `docs/benchmark_targets.md` | Get one external reviewer to confirm whether the 5-minute / 30-minute review path is clear. |
| CI / smoke workflow | Smoke-tested target | `.github/workflows/smoke.yml` | Keep CI lightweight; do not treat CI success as physics validation. Add deterministic artifact summaries later. |
| Plasma operating point | Screening-level / preliminary support; DIII-D mesh/operator and short serial-topology solution convergence supported; provisional GEQDSK-derived `Jpar0` passes a total-current consistency check and finite-response test | `diiid_bout_operator_validation.py`, `diiid_bout_elm_solution_convergence.py`, `diiid_jpar0_reconstruction.py`, `diiid_jpar0_elm_response.py`, corresponding `validation_runs/` outputs | Run exact X-point topology with 14 MPI ranks, independently verify `Jpar0`, and perform longer linear growth-rate and nonlinear checks. |
| Experimental precursor timing | Preliminary support; FAIR-MAST public diagnostics support a timing prerequisite for preventative control in a reduced-order proxy | `FAIR_MAST_TCT_VALIDATION_SUMMARY.md`; `fair_mast_claim_gate.py`; FAIR-MAST precursor, null, fresh-trigger, morphology, OMV, RMP-analog, and external-review-packet outputs | Expert-review event labels and trigger timing; obtain measured actuator response or machine-specific causal intervention data. |
| TCT control response | Preliminary support / reduced-order only; FAIR-MAST forward surrogate favors standing bias + fast bounded boost, while RMP analog is directionally supportive but underpowered | TCT proxy scripts; `fair_mast_tct_forward_surrogate.py`; `fair_mast_tct_forward_sensitivity.py`; `fair_mast_rmp_causal_analog.py`; corresponding `validation_runs/` outputs | Precommit a larger scenario-matched or randomized actuator comparison with independent event labels; obtain DIII-D/FDP actuator and diagnostic channels for a machine-specific causal test. |
| Closed-loop BOUT++ current-sheet trigger bridge | `PASS_WITH_REDUCED_MODEL_BOUNDARIES`; nominal/fine-grid triggers reduce peak and integrated current while delayed cases preserve timing falsification boundary | `closed_loop_tct_trigger_validation.py`; `validation_runs/closed_loop_tct_trigger_default/closed_loop_trigger_report.md`; `m3dc1_diagnostic_contract.json` | Replace reduced `J`/`dJdt` diagnostics with authorized M3D-C1 fields or experimental magnetic diagnostics. |
| Dedalus current-sheet falsification | Reduced-MHD toy support with caveats; combined smoothing-plus-bias retains positive island/component reductions across compact resolution/timestep/prominence checks | `validation_models/dedalus_current_sheet/`; `validation_runs/dedalus_current_sheet_biased_tct_falsification_study/ARTIFACT_NOTES.md` | Add topology-based island diagnostics, broader convergence, and defensible source-term physics before treating results as actuator-like. |
| Current-sheet / plasmoid suppression | Reduced-model evidence / needs expert review | BOUT++ current-sheet ladder, closed-loop trigger run, Dedalus matrix/sweep/resolution/falsification outputs | Map thickness/aspect-ratio/plasmoid-marginality variables to accepted reduced-MHD or reconnection diagnostics and independent topology measures. |
| Liquid-lithium surface stability | `REDUCED_MODEL_PRIORITIZATION_ONLY`; deterministic scenario matrix supports prioritizing capillary/porous confinement, wetting microtexture, plasma/ion-wind boundary damping, and magnetic damping for bench tests | `LIQUID_LITHIUM_STABILIZATION_LITERATURE.md`; `scripts/run_liquid_lithium_stability.py`; `validation_runs/liquid_lithium_stability_default/` | Replace scalar reduced terms with measured lithium wetting, vapor-film, bubble/coalescence, magnetic-field, and plasma-boundary experiments. |
| Machine EFIT / GEQDSK inputs | Preliminary support; DIII-D GEQDSK/EFIT anchor and probe/smoke/convergence artifacts exist | `validation_inputs/`, `validation_runs/geqdsk_efit_baseline_default`, DIII-D BOUT/operator/Jpar0 runs, and companion `CaMaLabs/M3DC1` work where present | Run exact X-point topology on supported Linux/HPC; require experimental diagnostics before promoting claims. |
| Liquid lithium wall moderation | Speculative / screening-level | `fusion_engine_v5/engine/lithium_wall.py` and related scoring logic where present | Separate wall survivability from MHD claims; add thermal-hydraulic and material compatibility checks. |
| Blanket / TBR estimate | Screening-level | `fusion_engine_v5/blanket/`, OpenMC-style bridge files where present | Run explicit finalist cases with documented geometry, materials, particle counts, and uncertainty. |
| M3D-C1 bridge / public C1.h5 | Harness/proxy/integration support only; real public `C1.h5` integration was useful but fails reactor-relevant hard gates | `M3DC1_BOUT_GEQDSK_VALIDATION_SUMMARY.md`; `validation_runs/m3dc1_bout_cross_validation_default`; companion `CaMaLabs/M3DC1` reports | Replace proxy artifacts with authorized M3D-C1 inputs/outputs or reviewer-supported benchmark cases. |
| NotebookLM audio overview | Front-facing narrative/review aid | `validation_runs/notebooklm_audio_review_default/` | Keep claim-boundary note visible; do not cite audio as validation evidence. |
| Event severity / survivability | Screening-level proxy | Monte Carlo / event severity logic where present | Compare assumptions against ELM / disruption / reconnection literature or simulation outputs. |
| Plant power balance | Screening-level | power-balance modules and optimizer scoring where present | Separate physics validation from economic scoring; document all assumptions. |
| Evolutionary candidate search | Implemented screening workflow | optimizer scripts and generated candidate outputs | Add deterministic seeds, manifests, and small reproducible examples. |
| Historical logs / backups / generated outputs | Provenance only unless specifically referenced | `run.log`, `overnight_campaign.log`, `*.bak`, `*.broken`, `gen_*`, `validation_runs/*` | Preserve but index as historical; do not require reviewers to infer current claims from these files. |

## What can be claimed from this repo

The repository currently supports this conservative claim:

> A public, provenance-preserving workflow has been implemented to screen fusion blanket / lithium-wall / TCT-coupled design candidates, test timing prerequisites on public FAIR-MAST diagnostics, run reduced-MHD BOUT++/Dedalus current-sheet falsification studies, and organize artifacts for higher-fidelity OpenMC, M3D-C1, JOREK, NIMROD, or comparable expert review.

## What should not be claimed yet

The repository does not yet prove that:

- TCT suppresses real tokamak plasmoids or ELMs.
- The current retrospective MAST precursor trigger is reliable enough for real-time control.
- The six-shot measured-RMP association proves that a TCT actuator causes mitigation.
- Current-sheet thickness is a sufficient control target for tokamak edge events.
- Lithium-current coupling stabilizes a real plasma edge.
- The liquid-lithium surface-stability reduced matrix proves lithium retention,
  rewetting, vapor-film suppression, or reactor wall survivability.
- The Dedalus biased source term represents real liquid-lithium wall physics.
- Any optimizer-selected blanket is experimentally validated.
- Any finalist geometry has a validated tritium breeding ratio under final engineering constraints.
- Any candidate is an engineering-ready reactor design.
- Any local M3D-C1 / JOREK adapter work is equivalent to a supported high-fidelity physics result.

## Current recommended workflow

1. Start with the reviewer-facing documents:

```text
README.md
ROADMAP.md
VALIDATION_STATUS.md
docs/assumptions.md
docs/falsification_tests.md
docs/benchmark_targets.md
```

2. Treat historical logs, generated outputs, and backup files as provenance unless they are cited by a current validation report.

3. Run only lightweight smoke checks in generic CI.

4. Promote candidate outputs to explicit validation only when they include:

```text
- input assumptions,
- run command,
- random seed if applicable,
- code commit,
- output manifest,
- limitations note,
- interpretation boundary.
```

5. Validate blanket candidates with explicit OpenMC-style or comparable neutronics cases.

6. Validate TCT / edge-plasma behavior first with reduced benchmarks, then with M3D-C1, JOREK, BOUT++, NIMROD, or another suitable workflow only when supported by experienced users or documented benchmark cases.

## Highest-value next steps

1. Expert-review the FAIR-MAST event labels and precursor timing packet.
2. Replace reduced `J`/`dJdt` trigger diagnostics with authorized M3D-C1 fields or experimental magnetic diagnostics.
3. Add topology-based island diagnostics to the Dedalus/BOUT++ current-sheet studies.
4. Derive or cite a defensible liquid-metal current-coupling source term before interpreting biased Dedalus results as actuator-like.
5. Re-run the `be_outer_kill` blanket basin with fixed seeds, material definitions, uncertainty reporting, and a compact manifest.
6. Get one external MHD/reconnection reviewer to assess whether the current-sheet framing maps to accepted benchmark variables.


## Native M3D-C1 Smoke

A compact native M3D-C1 evidence package is recorded in `validation_runs/m3dc1_native_smoke/`. The public Princeton M3D-C1 checkout at commit `e17c0b7` builds with a local build-system compatibility patch adding `signal_handler.f90` to the CMake source list. The official `KPRAD_2D` case, staged with the bundled 48-partition mesh and `geqdsk`, reaches five timesteps and exits with `Stopped at 0`, producing a populated native `C1.h5` in the external run directory.

The official `C1ke` reference comparison does not pass: the generated file differs from the bundled reference by orders of magnitude in magnetic-energy columns under upstream `compare.py`. This is therefore classified as `NATIVE_M3DC1_EXECUTION_PASS_REFERENCE_REGRESSION_UNRESOLVED`, not M3D-C1 validation and not TCT validation.

C1ke column provenance was traced to `unstructured/output.f90`; the mismatch is already present in t=0 magnetic-energy diagnostics, so Level 4 remains unresolved and no M3D-C1 TCT validation claim is made.
