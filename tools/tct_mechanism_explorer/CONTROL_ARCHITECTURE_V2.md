# TCT Control Architecture V2

## Why this rung exists

The native M3D-C1 work has demonstrated transient sheet authority from the localized magnetic/flux operator, but fixed sustained magnetic forcing and simple current-redistribution forcing have not maintained favorable sheet conditioning.

A repo audit found an important translation gap: the successful reduced BOUT++ TCT model did not act on the magnetic/current-sheet variable alone. Its control layer acted on both the magnetic-flux/current-sheet equation and the vorticity equation. The current M3D-C1 mechanism explorer previously searched magnetic/current operators but no explicit native flow or momentum channel.

V2 closes that gap conservatively by using an **existing upstream M3D-C1 poloidal momentum source** rather than inventing a new vorticity equation term.

## Native flow/shear audit channel

M3D-C1 already exposes:

- `ipforce`: enable poloidal momentum source
- `aforce`: source magnitude
- `dforce`: source half-width
- `xforce`: source location in normalized radial coordinate
- `nforce`: `(1-x)` profile exponent

The explorer calls this mechanism family:

`poloidal_momentum_bias`

This is a **standing native momentum/flow source**. It is not claimed to be mathematically identical to the BOUT++ `omega_tct_strength` damping term, and it is not a calibrated liquid-lithium or hardware actuator. Its purpose is to answer a narrower question:

> Does native momentum/flow forcing supply sheet-control authority that is absent from magnetic/current forcing alone?

## New mechanism families

V2 adds:

1. `poloidal_momentum_bias`
   - standing native `ipforce` source
   - searches sign, bounded amplitude, width, radial position, and profile exponent

2. `hybrid_mag_momentum`
   - standing native poloidal-momentum bias
   - plus the already-used localized time-gated magnetic/flux perturbation
   - closest current native proxy to the earlier research posture of preventative bias plus bounded fast boost

3. `hybrid_mag_momentum_redistribution`
   - standing momentum bias
   - magnetic shaping
   - center/shoulder current redistribution
   - retained as a later, higher-complexity family; the clean V2 profile does not enable it initially

The original magnetic, current-drive, redistribution, and magnetic+redistribution families remain available.

## Clean first experiment

`explorer.control_v2.json` enables only:

- `magnetic_pulse`
- `poloidal_momentum_bias`
- `hybrid_mag_momentum`

This is intentional. The first result should tell us whether the missing native flow/shear channel matters before adding more actuator complexity.

The initial seeds are symmetric and predeclared:

- known magnetic seed: `mag_ctrl_amp = -0.01`
- momentum bias: `aforce = -0.005`
- momentum bias: `aforce = +0.005`
- magnetic seed + negative momentum bias
- magnetic seed + positive momentum bias

These amplitudes are normalized native exploration values, not physical actuator calibration.

## Scientific gates

The new momentum channel does **not** pass merely because it changes kinetic energy.

Kinetic-energy change is used only as a reachability signal showing that the native momentum source actually couples into the evolving M3D-C1 state.

A candidate still has to satisfy the existing sheet-authority gate:

- measurable positive sheet-width response
- favorable peak-current response
- favorable center-to-shoulder redistribution

Only candidates that pass short-response authority advance to sustained control and then topology evaluation.

The Pareto energy penalty now uses the larger of the magnetic- and kinetic-energy perturbations so a momentum candidate cannot appear artificially cheap simply because magnetic energy remains nearly unchanged.

## Relationship to the intended TCT controller

This is **not yet** the full feedback controller.

The intended later architecture remains approximately:

`standing bias -> early intervention -> aggressive bounded state -> hold/recovery`

with state decisions eventually driven by current-sheet observables such as `J`, `dJ/dt`, width, or `dW/dt`, plus realistic latency/hysteresis.

V2 first establishes whether a native standing flow/shear bias changes the actuator transfer function enough to justify building that state machine.

If `hybrid_mag_momentum` clearly outperforms magnetic-only control, the next rung should implement staged/state-dependent magnetic amplitude on top of the best bounded momentum bias rather than immediately increasing forcing amplitudes.

## Liquid-lithium boundary

The current physical mapping remains:

`LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED`

until a defensible normalized M3D-C1 magnetic command -> physical `Delta B [T]` transfer is available.

The Ruzic/Fiflis gate remains in the explorer and should be applied only after that dimensional bridge exists. Native `aforce` is likewise not interpreted as a physical lithium momentum transfer coefficient.

## Run

From a clone on `agent/tct-pulse-train-audit`:

```bash
cd tools/tct_mechanism_explorer
bash run_control_v2.sh
```

Optional larger search:

```bash
POPULATION=12 GENERATIONS=10 SEED=8776 bash run_control_v2.sh
```

Compact results are written to:

```text
validation_runs/tct_control_architecture_v2/
```

## Claim boundary

A positive V2 result would show that a native M3D-C1 momentum/flow source, alone or combined with the localized magnetic operator, improves control authority over the tested GEM current sheet. It would not establish that the upstream `ipforce` source is a literal TCT hardware model, that liquid lithium supplies this momentum channel, or that reactor/ELM stabilization has been demonstrated.
