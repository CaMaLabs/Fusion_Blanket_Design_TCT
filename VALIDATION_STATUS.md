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
| TCT control response | Screening-level / needs benchmark; real FAIR-MAST timing results favor preventative control; measured-RMP causal analog is directionally supportive but underpowered and does not test TCT control | TCT proxy scripts; `diiid_diagnostic_reconstruction.py`; `fair_mast_elm_precursor_validation.py`; `fair_mast_rmp_causal_analog.py`; corresponding `validation_runs/` outputs | Precommit a larger scenario-matched or randomized actuator comparison with independent event labels; obtain DIII-D/FDP actuator and diagnostic channels for a machine-specific causal test. |
| Current-sheet / plasmoid suppression | Needs benchmark / expert review | Reduced current-sheet and BOUT-style scaffolding where present | First test whether thickness / aspect-ratio / plasmoid-marginality variables map to accepted reduced-MHD or reconnection diagnostics. |
| Machine EFIT / GEQDSK inputs | Preliminary support | `validation_inputs/`, `validation_runs/`, and companion `CaMaLabs/M3DC1` work where present | Run on a conventional Linux/HPC host or supported environment; require experimental diagnostics before promoting claims. |
| Liquid lithium wall moderation | Speculative / screening-level | `fusion_engine_v5/engine/lithium_wall.py` and related scoring logic where present | Separate wall survivability from MHD claims; add thermal-hydraulic and material compatibility checks. |
| Blanket / TBR estimate | Screening-level | `fusion_engine_v5/blanket/`, OpenMC-style bridge files where present | Run explicit finalist cases with documented geometry, materials, particle counts, and uncertainty. |
| Event severity / survivability | Screening-level proxy | Monte Carlo / event severity logic where present | Compare assumptions against ELM / disruption / reconnection literature or simulation outputs. |
| Plant power balance | Screening-level | power-balance modules and optimizer scoring where present | Separate physics validation from economic scoring; document all assumptions. |
| Evolutionary candidate search | Implemented screening workflow | optimizer scripts and generated candidate outputs | Add deterministic seeds, manifests, and small reproducible examples. |
| Historical logs / backups / generated outputs | Provenance only unless specifically referenced | `run.log`, `overnight_campaign.log`, `*.bak`, `*.broken`, `gen_*`, `validation_runs/*` | Preserve but index as historical; do not require reviewers to infer current claims from these files. |

## What can be claimed from this repo

The repository currently supports this conservative claim:

> A public, provenance-preserving proxy workflow has been implemented to screen fusion blanket / lithium-wall / TCT-coupled design candidates and organize them for higher-fidelity OpenMC, reduced-MHD, BOUT++, M3D-C1, JOREK, or comparable expert review.

## What should not be claimed yet

The repository does not yet prove that:

- TCT suppresses real tokamak plasmoids or ELMs.
- The current retrospective MAST precursor trigger is reliable enough for real-time control.
- The six-shot measured-RMP association proves that a TCT actuator causes mitigation.
- Current-sheet thickness is a sufficient control target for tokamak edge events.
- Lithium-current coupling stabilizes a real plasma edge.
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

1. Add a deterministic minimal run that produces a small manifest and summary artifact.
2. Identify one reduced current-sheet / plasmoid benchmark to target.
3. Identify one explicit blanket neutronics sanity-check case.
4. Create `validation/manifests/` and `validation/reports/` outputs for new runs.
5. Open GitHub issues for the highest-priority falsification tests.
6. Get one external reviewer to answer the benchmark-selection question.
