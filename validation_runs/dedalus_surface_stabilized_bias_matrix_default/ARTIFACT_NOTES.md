# Surface-Stabilized Bias Matrix Notes

## Purpose

This matrix tests non-acoustic ways to make a prescribed biased TCT-style source
less sharp in a reduced-MHD Dedalus current-sheet toy benchmark. It covers
capillary/porous-substrate damping proxies, smooth segmented envelopes,
channelized source geometry, magnetic-stiffening attenuation, and pulse shaping.

Acoustic damping and active surface-wave cancellation were intentionally excluded
from this run.

## Strongest Island-Proxy Result

- Best final island proxy case: `smoothing_plus_prebiased_smooth_pulse`
- Final island proxy: `7`
- Reduction vs no-bias baseline: `0.766667`

## Lowest Nonzero Surface-Risk Proxy

- Lowest nonzero source-risk case: `magnetic_stiffened_bias`
- Max surface displacement risk proxy: `0.000202787`
- Ratio vs smooth standing source: `0.25`

## Caveats

- Reduced-MHD toy benchmark only.
- Prescribed flux-source terms only.
- No free-surface MHD.
- No liquid-lithium material physics.
- No capillary-wave, wetting, electrode, sheath, contact-resistance, or wall model.
- No tokamak geometry and no TCT validation claim.
- The surface-risk metric is a source-gradient/laplacian proxy, not a fluid
  displacement calculation.

## Next Work

- Replace source-risk proxies with a real free-surface or shallow-liquid model.
- Sweep source strength, pulse timing, smoothness, and channel count.
- Repeat at higher resolution and with independent topology diagnostics.
- Review the prescribed-source equations with Dedalus/reconnection experts.
