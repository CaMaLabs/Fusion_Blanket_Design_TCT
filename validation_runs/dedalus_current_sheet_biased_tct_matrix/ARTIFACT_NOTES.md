# Biased Dedalus TCT Matrix Artifact Notes

## Purpose

This matrix is a reduced-MHD toy stress test for current-sheet diagnostics and
TCT-style proxy controls. It compares a finite-pulse driven island-onset
baseline against smoothing-only, biased wall-current-only, and combined
smoothing-plus-bias proxy cases.

## Strongest Result

The strongest case in this matrix is `smoothing_plus_bias_positive`.

- Baseline final island proxy count: `30`
- `smoothing_plus_bias_positive` final island proxy count: `7`
- Reduction versus baseline: `76.7%`

This means the combined smoothing and positive biased wall-current proxy reduced
the final island/plasmoid proxy burden in this toy setup.

## Caveats

- This is a reduced-model toy benchmark only.
- The island onset is driven by a finite artificial source pulse.
- The bias term is a prescribed reduced-MHD flux-source proxy.
- There is no tokamak geometry.
- There is no wall physics.
- There is no liquid lithium model.
- There are no electrodes, contact resistance, free-surface effects, sheath
  physics, or material response.
- This is not validation of TCT.

## Needed Next

- Parameter sweep over bias strength, polarity, mode number, and trigger timing.
- Resolution check at higher `nx`/`nz`.
- Independent diagnostic check for magnetic-island topology beyond local extrema.
- Physics review of whether the reduced source terms map to any credible
  actuator/current-closure mechanism.
