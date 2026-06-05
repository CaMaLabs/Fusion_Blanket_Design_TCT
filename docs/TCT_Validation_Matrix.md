# TCT Validation Matrix

This document defines a conservative validation structure for TCT-related claims in this repository.

The purpose is to separate implemented code, exploratory simulation output, physically testable hypotheses, and speculative reactor extrapolations.

## Core claim under test

TCT is treated here as an auxiliary plasma-edge / current-sheet control hypothesis:

> A structured boundary, perturbation, or current-response layer may improve selected edge/MHD stability metrics over a conventional baseline without imposing unacceptable confinement, heat-flux, or engineering penalties.

This is not yet a validated reactor claim.

## Claim levels

| Level | Label | Meaning | Required support |
| --- | --- | --- | --- |
| L0 | Concept | Mechanism proposed in prose | Markdown explanation and diagrams |
| L1 | Toy model | Mechanism expressed with variables and simplified equations | Notebook, script, or derivation |
| L2 | Reproducible numerical proxy | Simplified simulation shows measurable trend | Committed script + result JSON |
| L3 | Baseline comparison | TCT case compared to a conventional equilibrium / non-TCT case | Baseline fixture + comparison metrics |
| L4 | External-code validation | BOUT++, M3D-C1-style, FreeGSNKE, OpenMC, or equivalent workflow used | Run script + logs + output summary |
| L5 | Experimental analog | Bench demo demonstrates related low-energy physics only | Photos/video + measurement notes |
| L6 | Reactor relevance | Extrapolated reactor benefit | Requires L3/L4 support and uncertainty bounds |

## Required result schema

Each validation run should produce a machine-readable summary like:

```json
{
  "case_id": "tct_edge_scan_001",
  "baseline_case": "baseline_axisymmetric_001",
  "tool": "boutpp_or_m3dc1_or_proxy",
  "claim_level": "L2",
  "tct_enabled": true,
  "geometry_description": "structured edge perturbation placeholder",
  "input_files": [],
  "metrics": {
    "growth_rate_relative_change": null,
    "mode_amplitude_relative_change": null,
    "core_confinement_proxy_change": null,
    "edge_heat_flux_peaking_change": null,
    "required_current_or_field": null
  },
  "pass_fail": "inconclusive",
  "failure_modes_observed": [],
  "notes": "Exploratory result; not a reactor validation."
}
```

## Pass / fail definitions

A TCT case should not be called positive unless it satisfies all required criteria for the relevant level.

### Minimum positive L2 proxy result

- A non-TCT baseline exists.
- The same model is run with and without the TCT term.
- At least one target instability or event-severity metric improves.
- No obvious compensating penalty dominates the result.
- The result is reproducible from committed scripts.

### Minimum positive L3 baseline comparison

- Baseline equilibrium is identified.
- Perturbation magnitude and geometry are defined.
- Sensitivity scan is included.
- There is a bounded operating window.
- Failure cases are reported, not hidden.

### Minimum positive L4 external validation

- External solver or accepted public workflow is used.
- Input files are committed or generation scripts are committed.
- Output logs and summary JSON are committed.
- Result includes baseline and TCT comparison.
- Claim wording remains limited to the simulated configuration.

## Metrics table

| Metric | Field | Desired result | Hard warning sign |
| --- | --- | --- | --- |
| Instability growth rate | `growth_rate_relative_change` | Negative | Improvement only appears after changing unrelated baseline parameters |
| Mode amplitude | `mode_amplitude_relative_change` | Negative or bounded | Energy moves into another dangerous mode |
| Core confinement proxy | `core_confinement_proxy_change` | Near zero or positive | Stability comes from destroying confinement |
| Edge heat-flux peaking | `edge_heat_flux_peaking_change` | Negative | Heat load becomes more localized |
| Required field/current | `required_current_or_field` | Plausible | Requires impossible current density or field strength |
| Tolerance sensitivity | `tolerance_sensitivity` | Bounded | Tiny misalignment flips result from helpful to harmful |
| Failure severity | `failure_modes_observed` | Known and documented | Disruption risk ignored |

## Failure modes to document

Every validation report should explicitly check for:

- degraded confinement,
- increased edge heat-flux peaking,
- mode coupling into a worse instability,
- sensitivity to coil/rib/field alignment,
- unphysical current density,
- unmanageable wall loading,
- overfitting to one toy equilibrium,
- and claims exceeding the model fidelity.

## Documentation rules

Use these labels in README files and result summaries:

- **Implemented** — code exists and runs.
- **Screened** — simulation proxy produced a reproducible result.
- **Compared** — result was tested against a baseline.
- **Externally validated** — result was tested with a recognized external workflow.
- **Speculative** — physically possible idea, but not yet supported by validation.
- **Rejected / harmful** — tested and performed worse than baseline.

## Current recommended status

Until stronger MHD validation is committed, TCT should be described as:

> Exploratory / hypothesis-level, with repository structure being upgraded toward baseline-comparison validation.

That wording is honest and defensible.
