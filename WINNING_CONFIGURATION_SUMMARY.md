# Winning Configuration Summary

This document is the reviewer-facing snapshot of the best current fusion configuration in this repository. It summarizes the strongest **screening / proxy / validation-basin** results currently visible in the repository history.

This is **not** a demonstrated reactor design and should not be cited as experimental proof of TCT, wall survival, net power, or final tritium breeding feasibility. It is the current best configuration to use as the mainline candidate for follow-on validation.

## Bottom line

The current best setup is:

> **DT tokamak concept with liquid-lithium-facing wall, lithium-current coupling retained as a hypothesis, `be_outer_kill` / `be_outer_killer` blanket basin, and Mirnov/toroidal-triggered standing-bias plus fast bounded-boost TCT control.**

In practical terms, the project should treat this as the current mainline reference configuration:

```text
Plasma / machine family: DT tokamak screening configuration
Wall: liquid lithium active
Lithium current proxy: li_current = 0.1
TCT state: enabled as auxiliary edge-event control hypothesis
TCT policy: standing preventative bias + fast bounded boost
Trigger: Mirnov / toroidal precursor logic
Blanket topology: be_outer_kill / be_outer_killer
Layer order: Be -> Li2O -> Li2O -> W_Ti_B4C_60_30_10_wt -> Be
Best split: (0.15, 0.20, 0.40, 0.15, 0.10)
Best blanket thickness region: ~1.25
Best outer axial cap region: ~0.6, with 0.8 and 1.0 still competitive
Representative plasma radius in OpenMC basin: 50 cm
Representative lithium thickness in OpenMC basin: 0.003 m
```

## Why this is the current winner

### 1. OpenMC blanket search converged on the Be-family basin

The OpenMC screening notes identify the current best blanket regime as:

- liquid lithium wall active,
- `li_current = 0.1`,
- TCT supervisor enabled,
- aggressive supervisor level,
- `severity_scale = 0.6`,
- blanket topology `be_outer_kill`,
- layer ordering `Be -> Li2O -> Li2O -> W_Ti_B4C_60_30_10_wt -> Be`,
- split `(0.15, 0.20, 0.40, 0.15, 0.10)`,
- blanket thickness region near `1.25`,
- outer axial cap around `0.6`,
- plasma radius `50 cm`,
- lithium thickness `0.003 m`.

The same notes rank the competitive topology basin as:

1. `be_outer_kill`,
2. `be_sandwich`,
3. `pbli_absorber_tail`.

PbLi remains useful as a variant for future hybrid checks, but it is not the current mainline winner.

Primary historical summary file:

```text
docs/todays_sweeps_2026-04-01.md
```

Related OpenMC / reactor-screening artifacts include:

```text
summary_all.csv
top25.json
scripts/run_openmc_ordering_ab_fast.py
reactor_*.json
gen_*/leaderboard.json
gen_*/pareto_front.json
```

Important caution: later `gen_*` outputs include failed or provenance-only reactor packets. Do not infer the winning blanket basin from a single failed `reactor_01.json`; use the explicit OpenMC ordering / sweep summaries and manifests.

### 2. FAIR-MAST control proxy favors Mirnov/toroidal triggering

The strongest current TCT-side result is not a reactor proof. It is a reduced-order control-policy result:

```text
standing preventative bias + fast bounded boost
triggered by clean Mirnov / toroidal precursor logic
```

The FAIR-MAST forward surrogate ranked `mirnov_toroidal_fast_boost` as the best realizable policy class, with about `51.5%` proxy loss reduction versus no control in the seeded forward surrogate.

The forward sensitivity sweep then found Mirnov/toroidal fast boost tied for best realizable policy in `320/320` swept scenarios and within 1% of best in `320/320` scenarios.

Primary current reports:

```text
FAIR_MAST_TCT_VALIDATION_SUMMARY.md
validation_runs/fair_mast_tct_forward_surrogate_default/fair_mast_tct_forward_surrogate_report.md
validation_runs/fair_mast_tct_forward_sensitivity_default/fair_mast_tct_forward_sensitivity_report.md
```

### 3. M3D-C1-side validation target froze the same basin

The companion M3D-C1 validation harness freezes Candidate-0 as:

```text
blanket topology: be_outer_killer
active TCT: enabled
liquid lithium layer: enabled
lithium current coupling: enabled
```

Representative Candidate-0 machine/control values in the M3D-C1-side handoff are:

```text
R = 5.5 m
a = 1.8 m
B0 = 7.2 T
Ip = 14.0 MA
kappa = 1.9
triangularity = 0.35
H98 = 1.35
greenwald_fraction = 0.83
target_betaN = 2.7
lithium_thickness = 0.0014 m
lithium_velocity = 2.2 m/s
lithium_current_proxy = 0.10
TCT translation mode = current_profile_broadening_proxy
control_strength = 0.60
upstream_factor = 0.75
edge_resistivity_modifier = 0.15
```

Companion repository artifact:

```text
CaMaLabs/M3DC1: validation/candidate0_be_outer_killer.json
```

## Current mainline configuration

Use this as the mainline v6 candidate until a newer manifest supersedes it:

| Subsystem | Current best choice | Validation level |
|---|---|---|
| Fuel cycle | DT | Mainline screening basis |
| Blanket topology | `be_outer_kill` / `be_outer_killer` | Best OpenMC screening basin |
| Blanket layer order | `Be -> Li2O -> Li2O -> W_Ti_B4C_60_30_10_wt -> Be` | Current winner from OpenMC ordering notes |
| Split | `(0.15, 0.20, 0.40, 0.15, 0.10)` | Best micro-sweep split found so far |
| Wall | Liquid lithium active | Implemented / hypothesis-coupled |
| Lithium current | `li_current = 0.1` / proxy `0.10` | Retained as hypothesis, not proven actuator |
| TCT control | Standing bias + fast bounded boost | Best reduced-order control proxy |
| Trigger | Mirnov/toroidal precursor logic | Best current FAIR-MAST proxy result |
| Closed-loop BOUT++ trigger bridge | J/dJdt reduced current-sheet trigger contract | `PASS_WITH_REDUCED_MODEL_BOUNDARIES`; reduced-model evidence only |
| TCT physical claim | Auxiliary edge-event control hypothesis | Not experimentally proven |
| p-B11 | Not mainline | Keep as later exploratory branch only |
| PbLi | Not current winner | Keep as future variant / hybrid check |

## What this configuration supports saying

Defensible:

> The current repository evidence favors a DT tokamak screening configuration using a liquid-lithium wall, `be_outer_kill` / `be_outer_killer` Be/Li2O/W-Ti-B4C/Be blanket basin, and Mirnov/toroidal-triggered standing-bias plus fast bounded-boost TCT proxy control as the mainline candidate for deeper validation.

Not defensible yet:

> This proves a reactor design, validates TCT experimentally, proves lithium-current stabilization, proves final TBR under engineering constraints, or demonstrates sustained net-power operation.

## Next validation priorities

1. Create a clean current OpenMC manifest separating successful ordering / sweep outputs from failed historical `reactor_*.json` provenance files.
2. Re-run the `be_outer_kill` basin with explicit current scripts, fixed seeds, material definitions, uncertainty reporting, and a compact machine-readable summary.
3. Preserve `be_sandwich` as the nearest blanket competitor.
4. Keep PbLi as a non-mainline physics variant.
5. Map the TCT current-profile / current-sheet language to accepted reduced-MHD, reconnection, peeling-ballooning, RMP, or edge-stability variables.
6. Continue using Mirnov/toroidal precursor logic as the current best control trigger until a cleaner SXR classifier beats it under false-trigger and latency penalties.
7. Replace the closed-loop reduced-MHD `J`/`dJdt` trigger bridge with authorized M3D-C1 fields or experimental magnetic diagnostics before claiming tokamak-grade validation.
