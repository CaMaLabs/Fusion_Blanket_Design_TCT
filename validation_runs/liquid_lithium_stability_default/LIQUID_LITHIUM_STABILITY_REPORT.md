# Liquid Lithium Surface Stability Reduced-Model Report

- Status: `REDUCED_MODEL_PRIORITIZATION_ONLY`
- Scenario count: `14`
- Best reduced-model scenario: `combined_porous_microtexture_plasma`

## What This Adds

This module translates three outside stabilization mechanisms into a deterministic reduced scenario matrix:

- ionized-gas / plasma-assisted surface damping as a boundary-layer shear damping proxy,
- liquid-surface stabilization / surfactant-like bubble coalescence suppression as a bubble-risk proxy,
- micro/nanotexture and capillary rewetting as vapor-film and retention proxies.

It is a bench-test prioritization layer, not a reactor or tokamak-grade validation result.

## Key Results

| Scenario | Regime | Margin | Final amplitude | Bubble risk | Vapor risk | Retention |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `free_lithium_pool_baseline` | unstable | -0.312 | 0.157 | 0.435 | 0.409 | 0.574 |
| `ribbed_substrate` | marginal | -0.051 | 0.108 | 0.379 | 0.331 | 0.682 |
| `porous_wick_cps_substrate` | stable | 0.500 | 0.049 | 0.200 | 0.182 | 0.878 |
| `microtextured_high_wetting_surface` | stable | 0.559 | 0.045 | 0.252 | 0.044 | 0.937 |
| `vapor_film_prone_hot_surface` | vapor-film dominated | -1.126 | 0.708 | 0.603 | 0.932 | 0.196 |
| `argon_cover_gas_only` | unstable | -0.258 | 0.145 | 0.411 | 0.409 | 0.582 |
| `weak_plasma_ion_wind_boundary_layer` | marginal | -0.100 | 0.116 | 0.368 | 0.409 | 0.600 |
| `combined_porous_microtexture_plasma` | stable | 1.286 | 0.016 | 0.056 | 0.000 | 1.000 |
| `falsification_high_heat_flux_vapor_blanketing` | vapor-film dominated | -0.806 | 0.510 | 0.535 | 1.000 | 0.395 |
| `falsification_insufficient_wetting` | unstable | -0.643 | 0.378 | 0.515 | 0.673 | 0.445 |
| `falsification_excessive_perturbation` | bubble-coalescence dominated | -0.007 | 0.728 | 0.679 | 0.194 | 0.606 |
| `falsification_plasma_shear_too_weak` | unstable | -0.605 | 0.239 | 0.491 | 0.610 | 0.475 |
| `falsification_porous_dryout_saturation` | vapor-film dominated | -0.505 | 0.372 | 0.422 | 0.744 | 0.488 |
| `falsification_magnetic_damping_absent` | unstable | -0.346 | 0.165 | 0.427 | 0.522 | 0.638 |

## Strongest Result

`combined_porous_microtexture_plasma` had the highest stability-margin ordering in this reduced matrix with margin `1.286` and retention score `1.000`.

The combined porous + microtexture + plasma case is the intended positive-control case. It improved stability margin by `1.598` relative to the free-pool baseline.

## Falsification Behavior

The high-heat-flux vapor-blanketing case produced `vapor-film dominated` behavior with vapor risk `1.000`.

Non-stable falsification cases:

- `falsification_high_heat_flux_vapor_blanketing`
- `falsification_insufficient_wetting`
- `falsification_excessive_perturbation`
- `falsification_plasma_shear_too_weak`
- `falsification_porous_dryout_saturation`
- `falsification_magnetic_damping_absent`

## Limitations

- No Navier-Stokes/free-surface MHD solve.
- No lithium wetting chemistry, corrosion, evaporation, impurity, or material-compatibility model.
- No acoustic model.
- No tokamak geometry, neutron environment, or plasma-edge coupling.
- Coefficients are transparent screening weights, not measured lithium parameters.

## Conservative Conclusion

The reduced model supports prioritizing capillary/porous confinement, wetting microtexture, argon/plasma boundary-layer damping, and magnetic damping for follow-up bench testing. It does not show that liquid lithium is stabilized in a reactor.
