# Funding Alignment Notes

This document frames the repository as a software and validation-pipeline project suitable for early-stage public funding discussions.

The most defensible funding target is not a full reactor claim. The defensible target is a reproducible validation pipeline for fusion concept screening and handoff to established simulation workflows.

## Recommended project framing

Working title:

> Fusion Validation Pipeline: open-source reproducibility and benchmark-generation workflow for fusion blanket, wall, and edge-control hypotheses.

One-sentence version:

> This project develops a reproducible software pipeline that converts early fusion design hypotheses into versioned assumptions, smoke-tested code, benchmark artifacts, and validation handoff packages for neutronics and MHD review.

Why this framing is stronger than pitching TCT alone:

- It makes the code pipeline the product.
- It treats TCT as a demonstration case.
- It invites falsification instead of requiring belief.
- It can produce useful outputs even if a specific physics hypothesis fails.
- It is easier for reviewers to map onto software, reproducibility, AI-for-science, and simulation-infrastructure programs.

## Realistic funding paths

### 1. DOE SBIR / STTR

Fit: strong, if a small business is formed.

Best angle:

> Develop an open-source validation and reproducibility pipeline for fusion simulation workflows, integrating surrogate screening, CI-visible smoke tests, benchmark-case generation, OpenMC-style neutronics outputs, and MHD-code handoff artifacts.

Why it fits:

- SBIR/STTR programs are intended for small-business R&D with commercialization potential.
- The pipeline can be positioned as a software tool for fusion startups, university groups, and independent validation teams.
- TCT can serve as the internal demonstration case without making unsupported reactor-level claims.

Likely requirements:

- Form a qualifying small business.
- Obtain UEI and SAM.gov registration.
- Register for Grants.gov / DOE submission systems as needed.
- Prepare a technical abstract, work plan, budget, commercialization plan, and team/resume package.
- For STTR, secure a research institution partner.

Phase I-style work package:

- Build deterministic smoke-test suite.
- Add assumption registry and falsification-test schema.
- Implement one neutronics benchmark export path.
- Implement one MHD / equilibrium benchmark handoff path.
- Produce public validation reports and machine-readable artifacts.

### 2. INFUSE

Fit: strong later, if a private company leads and a lab/university partner is identified.

Best angle:

> Private-sector fusion validation software project seeking national-lab or university support for benchmark selection, validation workflow review, and handoff to accepted fusion codes.

Why it fits:

- INFUSE is designed to connect private fusion companies with national-lab and university expertise.
- Modeling and simulation is an appropriate category for a validation-pipeline project.
- A narrow benchmark-selection request is more realistic than asking for broad concept endorsement.

Likely requirements:

- A company must be the applicant / lead.
- A lab or university partner must be willing to define the technical assistance package.
- The request should be narrow: benchmark selection, validation review, or code-handoff support.

Possible INFUSE work package:

- Select one edge-stability / MHD proxy benchmark.
- Select one blanket neutronics benchmark.
- Review the pipeline artifact format.
- Identify the minimum information needed for M3D-C1, JOREK, BOUT++, NIMROD, or comparable tools.

### 3. DOE Genesis Mission / AI-for-science opportunities

Fit: possible, but probably team-dependent.

Best angle:

> AI-assisted fusion validation pipeline that turns concept-level design notes and code repositories into structured, provenance-preserving benchmark artifacts for simulation and expert review.

Why it may fit:

- Genesis Mission-style initiatives focus on AI, scientific datasets, simulation acceleration, and national-lab-scale R&D workflows.
- Fusion plasma dynamics and scientific simulation are directly relevant to AI-for-science infrastructure.
- The pipeline could eventually support AI-assisted assumption extraction, test generation, benchmark matching, and validation triage.

Limitations:

- A solo independent submission is unlikely to be competitive.
- The project would need a team, institutional partner, or company partner.
- The pitch must be about scientific workflow acceleration, not a standalone reactor invention.

### 4. ARPA-E

Fit: possible later, not first.

Best angle:

> AI-assisted validation infrastructure that reduces the time from early fusion concept to falsifiable multi-physics benchmark.

Why it is not the first target:

- ARPA-E expects high-impact energy technology with a credible team and a clear path to technical milestones.
- The current repository needs stronger validation artifacts before it is ARPA-E-shaped.

What would make it more credible:

- External technical advisor.
- Reproducible benchmark artifacts.
- At least one successful independent run or review.
- Clear commercialization path.

### 5. DOE Fusion Energy Sciences academic programs

Fit: indirect.

Best angle:

> Support a university or lab collaborator with reproducibility tooling and benchmark-generation infrastructure.

Limitation:

- These opportunities are usually more natural for universities, national labs, and established research organizations than unaffiliated individuals.

## Least realistic near-term paths

- Milestone-Based Fusion Development Program.
- Direct full-device validation through M3D-C1 or JOREK without an institutional collaborator.
- Broad cold outreach asking senior researchers to evaluate the full TCT reactor concept.
- Any pitch that makes the unvalidated reactor concept the primary deliverable.

## Company formation checklist

If pursuing SBIR/STTR or INFUSE seriously, create a small company around the pipeline rather than around an unvalidated reactor claim.

Potential company focus:

> Fusion validation software, reproducibility tooling, benchmark generation, and simulation-readiness auditing.

Checklist:

- [ ] Choose entity type, likely LLC first unless investors require otherwise.
- [ ] Register entity in state.
- [ ] Obtain EIN.
- [ ] Obtain UEI.
- [ ] Register at SAM.gov.
- [ ] Create capability statement.
- [ ] Prepare one-page technical summary.
- [ ] Prepare 6-month Phase I work plan.
- [ ] Identify at least one academic or lab advisor.
- [ ] Identify at least one fusion startup or open-source fusion software user as a potential customer / letter-of-support source.

## Phase I concept outline

### Problem

Early fusion concepts and simulation workflows are often difficult to evaluate because assumptions, geometry, validation levels, and benchmark targets are scattered or undocumented.

### Proposed solution

Develop an open-source validation pipeline that converts concept-level fusion design work into reproducible, CI-tested, benchmark-ready artifacts for expert review.

### Technical objectives

1. Build an assumption registry and falsification-test schema.
2. Add deterministic smoke tests and CI-visible validation summaries.
3. Generate neutronics-ready blanket candidate artifacts.
4. Generate MHD / edge-stability handoff artifacts.
5. Create reviewer-facing reports that distinguish validated results from speculative assumptions.

### Demonstration case

Use the Fusion Blanket / TCT repository as the first demonstration case, while keeping the pipeline general enough for other fusion blanket, wall, and edge-control hypotheses.

### Expected Phase I outputs

- Public roadmap.
- CI smoke validation.
- Assumption and falsification-test documents.
- Benchmark target registry.
- Example validation artifacts.
- Phase II plan for broader tool integration.

## Outreach strategy

Do not ask reviewers to evaluate the entire concept.

Ask one of these narrow questions:

1. What is the smallest benchmark case this should target?
2. Is current-sheet thickness a meaningful control variable, or should this be reformulated in standard edge-stability terms?
3. What information would be required before a real M3D-C1 / JOREK / BOUT++ user could evaluate this?
4. Which assumption would you try to falsify first?

## Reviewer categories to target

Most realistic:

- mid-career edge-stability / ELM researchers,
- reduced-MHD / reconnection researchers,
- BOUT++, NIMROD, FreeGSNKE, EFIT, or OpenMC users,
- fusion software and open-science contributors,
- university researchers who publish benchmark or validation workflows.

Less realistic:

- lab directors,
- high-profile fusion CEOs,
- senior researchers with no direct software / benchmark interest,
- people whose work is unrelated to edge stability, MHD, neutronics, or reproducibility.

## Notes for public positioning

Use language like:

- conceptual and computational design study,
- validation pipeline,
- benchmark handoff,
- reproducibility scaffold,
- falsification path,
- hypothesis-level TCT framing.

Avoid language like:

- proven reactor design,
- solved ELMs,
- validated TCT reactor,
- direct proof of fusion viability,
- guaranteed plasma control method.
