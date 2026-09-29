# p-B11 / TCT Integration Track

## Purpose

This document folds the existing `experiments/pb11_advanced_design/` work back into the active TCT research program without allowing p-B11 surrogate assumptions to inherit validation from DT/MHD results.

The research program now has two coupled but separately claimed tracks:

1. **TCT stability/control track** — controller-in-loop, precursor timing, segmented/radial actuation, current redistribution, edge/MHD response, actuator latency, and experimental-shot analogs.
2. **p-B11 energy/particle track** — proton recirculation, p-B11 reaction yield, beam/target slowing, bremsstrahlung and electron losses, alpha transport/channeling, boron delivery, wall loading, and direct conversion.

A result may couple the two tracks, but it must retain the lower of the two applicable fidelity levels.

## Existing p-B11 state to preserve

The advanced p-B11 branch already contains reproducible optimizer searches, sensitivity/robustness studies, uncertainty stress cases, and an M3D-C1 handoff.

Important historical checkpoints:

- Early integrated Case H remained p-B11-negative (`pB11_net_delta ~= -0.60`) because burnup was too low; direct-conversion efficiency alone did not rescue it.
- Later surrogate optimization produced positive p-B11 contribution in configurations using long effective proton path length / recirculation, boron-rich target/wall handling, alpha channeling, and cavity/guidance assumptions.
- Robustness and uncertainty harnesses identified cavity quality, proton retention/recirculation, boron delivery, and alpha handling as sensitive assumptions.
- The existing M3D-C1 handoff correctly states that p-B11, direct-conversion, racetrack/guidance, and wall-channel effects are surrogate annotations rather than native M3D-C1 physics.

These results remain useful for prioritization, not for claiming p-B11 reactor validation.

## Integration rule

Every future TCT experiment should declare whether it is:

- `fuel_track: dt_baseline`
- `fuel_track: pb11_auxiliary`
- `fuel_track: pb11_primary`
- `fuel_track: fuel_agnostic_control`

For p-B11 cases, also declare a `pb11_fidelity` block identifying which quantities are native/externally modeled versus surrogate.

Recommended fields:

```json
{
  "fuel_track": "pb11_auxiliary",
  "pb11_fidelity": {
    "reactivity": "surrogate|tabulated|kinetic",
    "proton_slowing": "surrogate|transport|kinetic",
    "proton_recirculation": "surrogate|orbit|particle",
    "bremsstrahlung": "proxy|radiation_model",
    "alpha_transport": "surrogate|orbit|particle",
    "alpha_channeling": "surrogate|wave_particle",
    "direct_conversion": "surrogate|electrostatic_particle",
    "boron_delivery": "surrogate|materials_transport"
  }
}
```

No p-B11 result may be labeled externally validated merely because the TCT/MHD portion ran in M3D-C1, BOUT++, FreeGSNKE, or another external code.

## Shared TCT mechanisms to transfer into p-B11

### 1. Precursor-aware controller

Retain the active control architecture:

`standing preventative bias -> precursor estimate -> response-time feasibility gate -> bounded boost -> NO ACTION if too late`

p-B11 should use the same causal controller timing rather than a separately tuned arbitrary pulse schedule.

The p-B11 track should report whether p-B11-specific operating conditions alter:

- precursor lead-time distribution,
- actuator reachability,
- required standing bias,
- current-sheet/ELM severity,
- particle/confinement loss rates,
- wall heat-flux localization.

### 2. Segmented radial/poloidal electrodes

Use independently driven electrode zones rather than a global scalar bias wherever the model supports electric-field actuation.

Required quantities:

- `V_i(t)` for each electrode zone,
- `E_r(r,z,t)` and relevant poloidal/axial components,
- `v_ExB = E x B / B^2`,
- local shear-layer position/strength/sign,
- voltage, current, power, and slew limits.

For p-B11, additionally record whether the electrode solution changes proton retention, alpha collection, electron loss, direct-conversion geometry, or boron transport. Those couplings are hypotheses until explicitly modeled.

### 3. Controller generalization

A controller candidate should be evaluated in at least three modes where practical:

- DT/TCT baseline,
- same plasma/MHD model with p-B11 auxiliary annotations disabled,
- p-B11-coupled case with only the justified p-B11 modules enabled.

This is intended to identify whether a controller benefit is genuinely fuel-agnostic or only appears because a surrogate p-B11 assumption changes the objective.

## p-B11 validation ladder

### P0 — historical surrogate reproduction

Re-run the committed p-B11 advanced-design reference cases and confirm deterministic reproduction of the archived tables/JSON.

### P1 — assumption ablation

Ablate one p-B11 enabling assumption at a time:

- proton recirculation/path length,
- cavity/guidance quality,
- boron target/wall loading and feed efficiency,
- bremsstrahlung/electron-loss treatment,
- alpha channeling,
- direct conversion,
- wall/graphene channel assumptions.

The output must distinguish positive p-B11 contribution from positive total DT-assisted reactor power.

### P2 — physically grounded reduced models

Replace the largest surrogate assumptions one-by-one with traceable physics:

1. tabulated p-B11 reactivity / cross-section integration,
2. proton stopping/slowing and pitch-angle scattering,
3. orbit/recirculation loss model,
4. radiation/bremsstrahlung balance,
5. alpha orbit/escape/deposition model,
6. electrostatic direct-conversion accounting,
7. boron source/transport and impurity penalty.

### P3 — TCT-coupled particle/control study

Couple the physically grounded p-B11 reduced modules to TCT controller outputs and segmented-field profiles. Test whether stability improvements survive when particle/radiation losses are included.

### P4 — independent solver / experiment analog

Use an external particle/transport/radiation workflow or suitable experimental p-B11 data where available. Keep MHD validation and p-B11 particle/energy validation as separate claim axes.

## Metrics to add to TCT runs when p-B11 is active

- `pb11_gross_power`
- `pb11_net_delta`
- `pb11_power_fraction`
- `proton_burnup_fraction`
- `proton_loss_fraction`
- `proton_energy_retention`
- `effective_proton_path_length`
- `recirculation_power`
- `bremsstrahlung_power`
- `electron_loss_power`
- `alpha_yield`
- `alpha_escape_fraction`
- `alpha_channeling_power`
- `direct_conversion_power`
- `direct_conversion_efficiency`
- `boron_source_rate`
- `boron_radiation_penalty`
- `wall_heat_load_pb11`

Controller/MHD metrics remain mandatory and should not be replaced by these quantities.

## Stop conditions / falsification gates

Treat the p-B11 branch as weakened or rejected for a tested configuration when any of the following persists after physically grounded modeling:

- positive `pb11_net_delta` requires implausible proton recirculation or confinement,
- radiation/electron losses erase the p-B11 contribution,
- alpha extraction/channeling requires unmodeled ideal coupling to remain positive,
- boron delivery or impurity radiation becomes incompatible with the TCT/MHD operating window,
- segmented fields that improve MHD substantially worsen proton/alpha confinement or conversion,
- the result is positive only because of a surrogate parameter with no defensible physical mapping.

Negative results are retained and reported; thresholds are not loosened merely to recover a positive design.

## Immediate research priority

The next p-B11/TCT work should not be another unconstrained optimizer sweep. The highest-value step is to reproduce the strongest archived p-B11 candidate and then replace its proton-recirculation / effective-path-length assumption with a physically grounded loss/slowing model while applying the current precursor-aware segmented TCT controller.

This gives a direct answer to the most important unresolved question: whether the p-B11 gain survives when the dominant enabling particle-retention assumption is made less idealized.
