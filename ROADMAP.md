# Roadmap: Fusion Validation Pipeline

This project should be evaluated first as an open-source validation and reproducibility pipeline for fusion concept screening, not as a completed reactor claim.

The near-term objective is to make speculative fusion design ideas easier to falsify, reproduce, and hand off to higher-fidelity tools.

## Core deliverable

A reproducible code pipeline that can move from concept-level design variables to reviewable validation artifacts:

1. define assumptions and geometry candidates,
2. run fast screening / surrogate calculations,
3. preserve candidate outputs and provenance,
4. export benchmark-style artifacts,
5. connect blanket candidates to neutronics validation,
6. connect plasma-control hypotheses to MHD / edge-stability validation targets,
7. publish CI-visible smoke tests and result summaries.

TCT is the first demonstration case. The pipeline should eventually support other fusion blanket, wall, and edge-control hypotheses.

## Why this exists

Independent or early-stage fusion ideas often fail at the transition between concept notes and credible simulation review. The missing layer is usually not ambition; it is reproducibility:

- assumptions are hard to locate,
- geometry is not encoded cleanly,
- validation level is unclear,
- outputs are not versioned,
- benchmark targets are missing,
- and external reviewers cannot quickly identify what would falsify the idea.

This repository is intended to make that transition explicit.

## Development phases

### Phase 0 — Public provenance and scope control

Status: in progress

Goals:

- Maintain timestamped public development history.
- Separate validated code paths from hypothesis-level claims.
- Keep public wording conservative and technically reviewable.
- Identify the minimum assumptions required for each candidate.

Deliverables:

- `README.md` with validation status and review path.
- `PROVENANCE.md` and `CITATION.cff`.
- Public-positioning and validation-matrix documentation.
- GitHub Actions smoke workflow.

### Phase 1 — Repository hygiene and smoke validation

Status: in progress

Goals:

- Ensure Python files compile in CI.
- Install dependencies in a clean GitHub Actions runner.
- Add lightweight smoke tests that do not require expensive simulation resources.
- Make failures visible without overstating validation.

Deliverables:

- `.github/workflows/smoke.yml`.
- Minimal deterministic test cases.
- Machine-readable summary artifacts where possible.
- Clear skip behavior for heavyweight tools.

### Phase 2 — Assumption registry

Status: planned

Goals:

- Collect all physical and engineering assumptions in one reviewable location.
- Classify assumptions as measured, literature-derived, estimated, or speculative.
- Link each assumption to a falsification path.

Planned files:

- `docs/assumptions.md`
- `docs/falsification_tests.md`
- `docs/benchmark_targets.md`

Example assumption categories:

- blanket material stack,
- first-wall / liquid-lithium behavior,
- heat-flux handling,
- tritium breeding ratio,
- edge-current / current-sheet framing,
- magnetic or electrostatic channeling assumptions,
- manufacturability constraints.

### Phase 3 — Benchmark target selection

Status: planned

Goals:

- Identify small, defensible benchmark cases before attempting full-device validation.
- Prefer open or well-documented cases where external reviewers can understand the setup.
- Avoid unsupported claims of M3D-C1, JOREK, or OpenMC validation until a case is actually run and documented.

Candidate validation directions:

- OpenMC-style neutronics for blanket finalist candidates.
- FreeGSNKE / EFIT-style equilibrium translation where appropriate.
- BOUT++ or reduced-MHD proxy cases for edge / instability framing.
- M3D-C1 or JOREK only through expert-supported collaboration or a documented benchmark path.

### Phase 4 — Exportable validation artifacts

Status: planned

Goals:

- Produce artifacts that another person can inspect without guessing what the code did.
- Store run parameters, outputs, plots, summaries, and provenance together.
- Make validation state machine-readable where possible.

Planned outputs:

- `validation/results/*.json`
- `validation/results/*.csv`
- `validation/reports/*.md`
- geometry / material-stack exports,
- run manifests,
- CI summaries.

### Phase 5 — External review loop

Status: planned

Goals:

- Convert passive repository traffic into actionable technical critique.
- Invite falsification rather than agreement.
- Track unresolved physics objections as issues.

Desired reviewer actions:

- point out invalid assumptions,
- suggest better benchmark cases,
- identify missing nondimensional parameters,
- recommend a more standard formulation,
- propose a minimal simulation that could disprove the framing.

### Phase 6 — Funding-ready pipeline package

Status: planned

Goals:

- Package the repository as a software pipeline suitable for SBIR/STTR, INFUSE-style partnership, or AI-for-science funding.
- Make the code pipeline the primary product.
- Treat TCT as the first use case rather than the sole deliverable.

Potential project framing:

> Open-source validation and reproducibility pipeline for fusion concept screening and handoff to higher-fidelity neutronics and MHD workflows.

## Near-term checklist

- [x] Add conservative README review path.
- [x] Add GitHub Actions smoke workflow.
- [ ] Add assumptions registry.
- [ ] Add falsification-test document.
- [ ] Add benchmark-target document.
- [ ] Add deterministic minimal test data.
- [ ] Add CI artifact summaries.
- [ ] Add funding-alignment document.
- [ ] Identify one credible MHD benchmark target.
- [ ] Identify one credible OpenMC blanket benchmark target.

## What would count as progress

The project advances if it makes any of the following easier:

- an expert can find a wrong assumption quickly,
- an outside developer can reproduce a smoke run,
- a reviewer can identify the next benchmark case,
- a lab or university partner can see a bounded work package,
- an SBIR/STTR or INFUSE proposal can describe the software pipeline without relying on unvalidated reactor claims.

## What would count as failure

The project should be considered unsuccessful, or at least in need of reformulation, if:

- the TCT framing cannot be mapped onto standard edge-stability or reconnection language,
- the current-sheet / thickness variables are not useful control targets,
- the proposed wall / blanket stack fails basic heat-flux or neutronics constraints,
- the pipeline cannot produce reproducible artifacts,
- or external reviewers cannot determine what is being claimed and what is still speculative.

Failure modes should be documented rather than hidden. A negative result still improves the pipeline if it produces a clear falsification path.
