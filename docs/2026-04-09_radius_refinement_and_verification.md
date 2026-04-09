# Radius Refinement, Challenger Comparison, and Liquid-Wall Proxy Results (2026-04-09)

## Baseline before radius refinement

Frozen neutronics baseline:

- Topology: `be_outer_kill`
- Ordering: `Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be`
- Split: `(0.15, 0.20, 0.40, 0.15, 0.10)`
- Blanket thickness: `1.25`
- Outer axial cap: `0.6`
- Liquid lithium wall active
- `li_current = 0.1`
- TCT supervisor enabled, aggressive
- `severity_scale = 0.6`

Frozen 50 cm verification returned approximately:

- `TBR_openmc ~= 2.2226`
- `attenuation ~= 0.99942`
- `gradient ~= 0.99983`
- `front_heating_frac ~= 0.221`
- `wall_load ~= 498` (with larger raw load values also reported upstream)
- `wall_temp ~= 29470`

Interpretation: strong neutronics, but thermal/load side still severe.

## Baseline vs challengers

A focused challenger comparison was run against the frozen `be_outer_kill` baseline:

1. baseline
2. more outer axial cap
3. thicker blanket
4. heat-inward split tweak
5. thicker blanket + more outer axial cap

Result: the original frozen baseline remained the reference design. None of the challengers beat it on combined profile.

## Liquid-wall proxy correction

A conservative liquid-wall proxy was applied to give the flowing lithium wall credit for:

- heat spreading
- hotspot suppression
- partial self-healing / sacrificial buffering

Representative corrected outputs for the 50 cm frozen baseline were approximately:

- `spread_credit = 0.35`
- `healing_credit = 0.28`
- `corrected_wall_load ~= 666.3`
- `corrected_wall_temp ~= 21734.8`
- `corrected_front_heating_frac ~= 0.1865`
- `corrected_fail_rate ~= 0.00936`

Interpretation: the liquid wall plausibly helps, but does not fully rescue the thermal side on its own.

## Radius sweep (first-principles lever)

To reduce thermal load without speculative materials assumptions, the baseline was re-run at larger plasma radii while holding the blanket architecture fixed.

Sweep:

- `radius_cm = 50, 55, 60, 65`

### Key outcomes

#### 50 cm
- `TBR_openmc ~= 2.2226`
- `wall_load ~= 825.18`
- `wall_temp ~= 29470.85`

#### 55 cm
- `TBR_openmc ~= 2.2155`
- `wall_load ~= 619.97`
- `wall_temp ~= 22141.89`
- `net_electric ~= 3824.64`

#### 60 cm
- `TBR_openmc ~= 2.2057`
- `wall_load ~= 477.54`
- `wall_temp ~= 17054.89`
- `net_electric ~= 3470.41`

#### 65 cm
- `TBR_openmc ~= 2.2095`
- `wall_load ~= 375.60`
- `wall_temp ~= 13414.13`
- `net_electric ~= 3170.38`

### Interpretation

Increasing radius clearly reduces thermal load and wall temperature while only modestly degrading neutronics.

- `50 cm` remains the best neutronics point.
- `60 cm` gives the strongest thermal relief in the tested compromise range.
- `55 cm` is the best overall engineering compromise because it preserves more TBR and net electric while still significantly reducing wall load and wall temperature.

## 55 cm vs 60 cm head-to-head

A direct 55 vs 60 cm comparison, including liquid-wall proxy correction, showed:

### 55 cm
- `TBR ~= 2.2155`
- `ATTN ~= 0.99971`
- `GRAD ~= 0.99989`
- `front_heat_raw ~= 0.2226`
- `front_heat_corr ~= 0.1857`
- `wall_load_raw ~= 619.97`
- `wall_load_corr ~= 507.63`
- `wall_temp_raw ~= 22141.89`
- `wall_temp_corr ~= 16329.64`
- `net_electric ~= 3824.64`

### 60 cm
- `TBR ~= 2.2057`
- `ATTN ~= 0.99961`
- `GRAD ~= 0.99984`
- `front_heat_raw ~= 0.2235`
- `front_heat_corr ~= 0.1863`
- `wall_load_raw ~= 477.54`
- `wall_load_corr ~= 391.99`
- `wall_temp_raw ~= 17054.89`
- `wall_temp_corr ~= 12577.98`
- `net_electric ~= 3470.41`

### Selected new reference candidate

The current best overall compromise is now:

- Topology: `be_outer_kill`
- Ordering: `Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be`
- Split: `(0.15, 0.20, 0.40, 0.15, 0.10)`
- Blanket thickness: `1.25`
- Outer axial cap: `0.6`
- `radius_cm = 55`
- Liquid lithium wall active
- `li_current = 0.1`
- TCT supervisor aggressive
- `severity_scale = 0.6`

## Recommended next verification path

1. Freeze the `55 cm` candidate as the new main reference.
2. Re-run full verification with any liquid-wall-aware engineering correction kept explicit as a proxy, not hidden in the raw result.
3. Run a **power-normalized radius check** if possible, to confirm the benefit is not an artifact of how geometry scales in the current reactor model.
4. Add a **deposition-peakedness / local heating concentration metric** to the OpenMC-side evaluation so that near-perfect attenuation is not rewarded blindly if it concentrates heat too aggressively.
5. Re-test one challenger against the frozen `55 cm` baseline:
   - either `60 cm` for thermal margin
   - or a slightly adjusted split around the same `55 cm` geometry if preserving TBR is the higher priority.
6. Only after that, consider introducing more detailed thermal-hydraulic proxy corrections or a better liquid-wall treatment.

## Current status statement

This does not solve fusion. It does establish a more credible, reproducible design basin and identifies `55 cm` as the current best compromise between neutronics and thermal burden within the present model stack.
