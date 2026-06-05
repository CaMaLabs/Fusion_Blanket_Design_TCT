# HW2D Cross-Code Validation

- Status: `HW2D_BOUT_HW_CROSS_CODE_SUPPORTED`
- Started: `2026-06-05T04:53:50.341326+00:00`
- BOUT++ source: `/root/Fusion_Blanket_Design_TCT/validation_runs/bout_hw_turbulence_sweep_default`
- HW2D-style rows: `16`

## What This Validates

This is an open reduced-turbulence cross-check. It compares the existing BOUT++ Hasegawa-Wakatani fixed-control sweep with an independent pseudo-spectral HW2D-style implementation using the same reduced-gradient TCT proxy.

## What This Does Not Validate

This is not an experimental EFIT validation, not a machine-geometry MHD run, and not a wall-distance M3D-C1 fix. It tests directional ordering in reduced turbulence only.

## Fixed-Control Cross-Code Ordering

| Grid | BOUT++ max-energy monotonic | HW2D max-energy monotonic | BOUT++ integrated reduction | HW2D integrated reduction |
| --- | ---: | ---: | ---: | ---: |
| base | True | True | 56.95% | 48.61% |
| coarse | True | True | 55.33% | 48.60% |

## HW2D Timing Ordering

| Grid | Best case | Ordering by integrated energy | Moderate beats late strong |
| --- | --- | --- | ---: |
| base | `steady_strong` | `steady_strong < over_control < steady_moderate < late_strong < uncontrolled` | True |
| coarse | `steady_strong` | `steady_strong < over_control < steady_moderate < late_strong < uncontrolled` | True |

## Interpretation

PASS: BOUT++ and the independent HW2D-style solver agree on the fixed-control reduced-gradient ordering, and the HW2D timing check preserves the expected result that moderate early control beats late strong control. The timing check does not prove that moderate control is globally optimal; in this reduced model, steady strong control has the lowest integrated energy, while over-control remains an unresolved actuator-model question.
