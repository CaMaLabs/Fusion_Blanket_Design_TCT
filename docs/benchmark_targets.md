# Benchmark Target Registry

This document lists candidate benchmark directions for turning broad TCT / blanket claims into bounded validation work.

No benchmark listed here should be interpreted as completed validation until an actual run, configuration, output manifest, and review note are committed.

## Benchmark selection criteria

A good first benchmark should be:

- small enough to reproduce,
- documented enough for external review,
- connected to one specific assumption,
- independent of full-reactor claims,
- and capable of producing a negative result.

## Plasma / MHD benchmark directions

### Reduced-MHD current-sheet / tearing / plasmoid benchmark

Purpose:

- Test whether current-sheet thickness, aspect ratio, or plasmoid marginality are useful variables before using tokamak-specific TCT language.

Why first:

- The core TCT framing should be tested in the simplest setting possible.
- If the framing fails here, full tokamak validation is premature.

Desired output:

- parameter scan,
- growth / onset metric,
- current-sheet thickness or aspect-ratio proxy,
- summary JSON / CSV,
- reviewer-facing note.

Validation status:

- Planned.

### BOUT++ edge / drift-wave / reduced edge proxy

Purpose:

- Explore whether a reduced edge model can carry any TCT-like control variable or whether the framing should be translated into standard edge variables.

Why not first:

- BOUT++ or edge-specific work is more meaningful after the reduced current-sheet framing is clarified.

Desired output:

- minimal input deck,
- controlled parameter sweep,
- growth / transport / event-severity proxy,
- limitations note.

Validation status:

- Preliminary scaffolding exists in repository outputs; not treated as final validation.

### M3D-C1 / JOREK supported benchmark

Purpose:

- Eventually test a properly formulated edge / nonlinear-MHD question in a high-fidelity code environment.

Why later:

- Expert users have warned that these codes are difficult to use correctly without knowledgeable collaboration.
- Unsupported local adapter work should not be presented as a real M3D-C1/JOREK physics result.

Desired output:

- benchmark case identified by an expert,
- supported environment or collaborator,
- complete input manifest,
- post-processing plan,
- conservative interpretation note.

Validation status:

- Not yet validated.

## Blanket / neutronics benchmark directions

### Single finalist OpenMC-style neutronics sanity check

Purpose:

- Test whether one optimized blanket candidate survives explicit material / geometry / TBR review.

Why first:

- A single bounded finalist is easier to review than a full optimizer campaign.

Desired output:

- material stack manifest,
- simplified geometry export,
- TBR / heating / shielding summary,
- uncertainty notes,
- reason the candidate passed or failed.

Validation status:

- Planned / partial scaffolding.

### Candidate ranking robustness check

Purpose:

- Determine whether optimizer rankings are stable under reasonable changes in surrogate assumptions.

Desired output:

- top candidates under baseline assumptions,
- top candidates under perturbed assumptions,
- rank-shift summary,
- list of assumptions driving the ranking.

Validation status:

- Planned.

## Wall / materials benchmark directions

### First-wall heat-flux sanity check

Purpose:

- Separate wall survivability from plasma-control claims.

Desired output:

- heat-flux assumption table,
- material limit table,
- failure margins,
- list of missing data.

Validation status:

- Planned.

### Lithium-wall compatibility review

Purpose:

- Identify whether lithium-wall assumptions are plausible enough to remain coupled to the TCT demonstration case.

Desired output:

- compatibility note,
- evaporation / retention / maintenance concerns,
- reason to keep or decouple lithium from the MHD hypothesis.

Validation status:

- Planned.

## Reviewer questions

When asking external reviewers for help, use narrow questions such as:

1. What is the smallest benchmark case this should target?
2. Is current-sheet thickness a meaningful variable here, or should the framing be replaced?
3. Which code family is appropriate before attempting M3D-C1 or JOREK?
4. What input artifact would make this reviewable?
5. Which assumption would you falsify first?

## Current priority

The highest-priority benchmark is a reduced current-sheet / plasmoid-onset test that can determine whether the TCT framing is physically useful before more complicated tokamak-specific validation is attempted.
