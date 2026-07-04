# Dedalus Segmented Bias Actuator Matrix Notes

## Purpose

This run tests whether a prescribed segmented electrode-rib or mesh-like
edge-current source is a cleaner reduced-model substitute for the earlier smooth
standing wall-current bias proxy.

The motivation is engineering simplification: a solid rib/mesh current path
could, in principle, provide more deliberate `J x B` force direction than
flowing liquid lithium. This artifact only tests prescribed reduced-MHD source
shapes. It is not an electrode model, sheath model, liquid-metal MHD model,
wall-engineering model, or TCT validation.

## Cases

The matrix compares:

- no-bias baseline
- smoothing-only proxy
- smooth standing bias proxy
- 8-rib positive and negative segmented sources
- 4-rib positive segmented source
- low-strength 8-rib positive segmented source
- 8-rib mesh-like source and low-strength mesh-like source
- phase-shifted/phase-locked 8-rib source
- smoothing plus smooth, rib, and mesh variants

## Key Result

The smooth standing bias remained the strongest reduced-model source shape in
this matrix:

- baseline final island proxy: `30`
- smooth standing bias final island proxy: `15`
- smoothing plus smooth standing bias final island proxy: `7`
- baseline final component proxy: `12`
- smooth standing bias final component proxy: `4`

## Falsification / Warning Result

The segmented rib variants were worse than baseline in this toy setup:

| Case | Final island proxy | Final component proxy |
| --- | ---: | ---: |
| `baseline` | `30` | `12` |
| `rib8_bias_positive` | `70` | `28` |
| `rib8_bias_negative` | `70` | `28` |
| `rib4_bias_positive` | `64` | `16` |
| `rib8_bias_positive_low_strength` | `57` | `17` |
| `phase_locked_rib8_positive` | `74` | `29` |
| `smoothing_plus_rib8_bias_positive` | `62` | `27` |

Interpretation: in this reduced model, sharp segmented rib forcing appears to
seed or amplify island-like morphology rather than suppress it. That does not
falsify real segmented electrodes, but it does falsify this particular sharp
rib source shape as a clean improvement over smooth bias.

## Mesh Result

The mesh-like source was less harmful than the rib source, but much weaker than
smooth standing bias:

- `mesh8_bias_positive`: `26` final island proxy, `12` component proxy
- `mesh8_bias_positive_low_strength`: `29` final island proxy, `12` component
  proxy
- `smoothing_plus_mesh8_bias_positive`: `26` final island proxy, `12` component
  proxy

This suggests mesh-like smoothing of the source shape may be safer than sharp
ribs, but this first proxy does not outperform the smooth standing source.

## Claim Boundary

Defensible:

> In the Dedalus reduced-MHD toy setup, a smooth standing edge-current source
> remains stronger than the first prescribed rib/mesh source proxies. Sharp rib
> segmentation is a useful falsification target because it increases island and
> component morphology proxies.

Not defensible:

> This proves segmented electrodes cannot work, validates liquid lithium, or
> establishes a physical actuator design.

## Next Step

If segmented bias remains interesting, the next reduced-model step should use
smoother physically motivated source shapes:

- broaden rib footprints,
- phase-lock to the driven island mode rather than impose many ribs,
- add current-density/energy penalties,
- sweep rib count, duty cycle, strength, and phase,
- compare against a topology-based island diagnostic.
