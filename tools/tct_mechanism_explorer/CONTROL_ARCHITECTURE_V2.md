# TCT Control Architecture V2

## Why this rung exists

The native M3D-C1 work has demonstrated transient sheet authority from the localized magnetic/flux operator, but fixed sustained magnetic forcing and simple current-redistribution forcing have not maintained favorable sheet conditioning.

A repo audit found an important translation gap: the successful reduced BOUT++ TCT model did not act on the magnetic/current-sheet variable alone. Its control layer acted on both the magnetic-flux/current-sheet equation and the vorticity equation. The current M3D-C1 mechanism explorer previously searched magnetic/current operators but no explicit native flow or momentum channel.

V2 closes that gap conservatively by using an **existing upstream M3D-C1 poloidal momentum source** rather than inventing a new vorticity equation term. It also adds a default-off staged magnetic selector so the explorer can test the intended `bias -> early -> aggressive -> hold` posture instead of only constant or single-pulse forcing.

## Native flow/shear audit channel

M3D-C1 already exposes:

- `ipforce`: enable poloidal momentum source
- `aforce`: source magnitude
- `dforce`: source half-width
- `xforce`: source location in normalized radial coordinate
- `nforce`: `(1-x)` profile exponent

The explorer calls this mechanism family `poloidal_momentum_bias`.

This is a **standing native momentum/flow source**. It is not claimed to be mathematically identical to the BOUT++ `omega_tct_strength` damping term, and it is not a calibrated liquid-lithium or hardware actuator. Its purpose is narrower:

> Does native momentum/flow forcing supply sheet-control authority that is absent from magnetic/current forcing alone?

## Staged magnetic selector

`install_control_v2_operator.py` makes a minimal extension to the already-local `imag_control` source. The new inputs are default-off. With:

`imag_control_staged = 0`

the pre-existing magnetic source behavior is retained.

With staged mode enabled, the effective magnetic command is selected from:

- `mag_ctrl_bias_amp`
- `mag_ctrl_early_amp`
- `mag_ctrl_aggressive_amp`
- `mag_ctrl_hold_amp`

using the ordered transition times:

- `mag_ctrl_t_early`
- `mag_ctrl_t_aggressive`
- `mag_ctrl_t_hold`
- existing `mag_ctrl_t_off`

This is **baseline-informed scheduled/open-loop staging**, not closed-loop feedback. It exists to test whether the previously identified control posture is materially different from holding one magnetic command continuously.

## New mechanism families

V2 adds:

1. `poloidal_momentum_bias`
   - standing native `ipforce` source
   - searches sign, bounded amplitude, width, radial position, and profile exponent

2. `hybrid_mag_momentum`
   - standing native poloidal-momentum bias
   - plus localized time-gated magnetic/flux perturbation

3. `staged_magnetic`
   - standing magnetic bias
   - early command
   - aggressive middle command
   - lower hold/recovery command

4. `staged_mag_momentum`
   - the staged magnetic waveform above
   - plus standing native poloidal-momentum bias
   - closest current native proxy to the intended preventative-bias + fast bounded boost + maintenance architecture

5. `hybrid_mag_momentum_redistribution`
   - standing momentum bias
   - magnetic shaping
   - center/shoulder current redistribution
   - retained as a later higher-complexity family rather than enabled in the clean V2 profile

The original magnetic, current-drive, redistribution, and magnetic+redistribution families remain available.

## Clean V2 experiment

`explorer.control_v2.json` enables:

- `magnetic_pulse`
- `poloidal_momentum_bias`
- `hybrid_mag_momentum`
- `staged_magnetic`
- `staged_mag_momentum`

The initial candidates are predeclared rather than outcome-tuned. They include the previously useful `mag_ctrl_amp=-0.01`, symmetric `aforce=+/-0.005` momentum probes, their magnetic hybrids, and a staged waveform seeded at approximately:

```text
bias       -0.002
early      -0.006
aggressive -0.012
hold       -0.003
```

with the staged hybrid adding the standing `aforce=-0.005` probe. These are normalized native exploration values, not physical actuator calibration.

## Scientific gates

The momentum channel does **not** pass merely because it changes kinetic energy.

Kinetic-energy change is used only as a reachability signal showing that the native momentum source actually couples into the evolving M3D-C1 state.

A candidate still has to satisfy the sheet-authority gate:

- measurable positive sheet-width response
- favorable peak-current response
- favorable center-to-shoulder redistribution

Only candidates that pass short-response authority advance to sustained control and then topology evaluation.

The Pareto energy penalty now uses the larger of the magnetic- and kinetic-energy perturbations so a momentum candidate cannot appear artificially cheap simply because magnetic energy remains nearly unchanged.

## Relationship to the intended TCT controller

V2 now represents the intended **control posture**, but it is still not a true feedback controller.

The staged families implement:

`standing bias -> early intervention -> aggressive bounded state -> hold/recovery`

on a frozen schedule. The eventual native feedback rung should replace those frozen transitions with state decisions driven by quantities such as `J`, `dJ/dt`, sheet width, `dW/dt`, and possibly reconnection-rate protection, together with explicit latency, dwell time, and hysteresis.

The correct next step depends on this V2 result:

- if momentum bias has no sheet authority, do not build feedback around it;
- if magnetic+momentum coupling clearly improves authority, promote the best bounded family to state-triggered control;
- if staged magnetic control beats constant/pulsed control, preserve the phase-dependent waveform rather than reverting to a DC command;
- if staged magnetic+momentum is strongest, that becomes the leading native TCT transfer-function candidate.

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

The runner installs/verifies the default-off staged selector, rebuilds `m3dc1_2d`, runs the Python tests, performs zero-actuation equivalence for every enabled family, and only then starts the evolutionary M3D-C1 search.

Optional larger search:

```bash
POPULATION=12 GENERATIONS=10 SEED=8776 bash run_control_v2.sh
```

Compact results are written to:

```text
validation_runs/tct_control_architecture_v2/
```

## Claim boundary

A positive V2 result would show that a native M3D-C1 momentum/flow source and/or staged magnetic waveform improves control authority over the tested GEM current sheet. It would not establish that `ipforce` is a literal TCT hardware model, that liquid lithium supplies this momentum channel, that normalized amplitudes have a physical actuator calibration, or that reactor/ELM stabilization has been demonstrated.
