# Today's Sweeps Summary (2026-04-01)

## Current best regime

The current best-performing blanket regime in the OpenMC search stack is:

- liquid lithium wall active
- `li_current = 0.1`
- TCT supervisor enabled
  - `supervisor_enabled = True`
  - `supervisor_level = "aggressive"`
  - `severity_scale = 0.6`
- blanket topology: `be_outer_kill`
- layer ordering: `Be -> Li2O -> Li2O -> W_Ti_B4C_60_30_10_wt -> Be`
- best split: `(0.15, 0.20, 0.40, 0.15, 0.10)`
- best blanket thickness region: `bt ~= 1.25`
- best outer axial cap region: `azo ~= 0.6` with `0.8` and `1.0` still competitive
- plasma radius: `50 cm`
- lithium thickness: `0.003 m`

## Important outcomes

### 1. Transport metrics are now visible
Earlier runs were misleading because attenuation and gradient were not propagating cleanly into the fast A/B runner. After bypassing that path and reading direct OpenMC validation output in the runner, the comparison started reflecting real transport behavior.

### 2. Winning basin
The top competitive topologies are now clearly:

1. `be_outer_kill`
2. `be_sandwich`
3. `pbli_absorber_tail` (still informative, but not competitive with the Be family)

### 3. Best split found so far
The strongest split from the micro-sweep is:

`(0.15, 0.20, 0.40, 0.15, 0.10)`

Interpretation:
- strong central breeder / diffusion body
- controlled entry region
- shaping / kill region in layer 4
- soft outer cleanup tail

### 4. PbLi status
PbLi remains interesting as a physics variant, but it is not winning the current score regime. It can be kept alive for future hybrid checks, but it is not the mainline design at the moment.

## Recommended immediate next step
Do the hybrid tweak first around the winning basin:

- keep the current winning split fixed
- mutate layer 4 / tail materials only
- compare `W_Ti_B4C` against `Be12Ti` and other light hybrids in the shaping region
- preserve `li_current = 0.1` during this phase for isolation

## Current status statement
This does **not** mean fusion is solved. It does mean the search has converged to a promising blanket design basin worth deeper validation.
