# Flying-Focus Audit Result — 2026-08-11

## Classification

**Promote to higher-fidelity kinetic modeling, with efficiency and trapping as explicit gates.**

The nominal flying-focus rephasing case is favorable in this screening model, but the result should not be interpreted as a reactor-gain prediction.

## Key findings

1. **FF injection alone is not the mechanism.** Reducing the injected proton spread from 8% to 3.7% changes cumulative resonance exposure only from 9.310 to 9.422 (+1.2%) when the beam is allowed to slow through repeated boron-sheet encounters.
2. **Repeated FF rephasing is the mechanism.** The nominal rephaser raises cumulative normalized resonance exposure to 30.956, 3.325x the conventional 675-keV beam and 4.538x the idealized 120-keV hold.
3. **Energy efficiency improves despite the extra rephasing energy.** Exposure per delivered proton MeV rises from 13.793 for the conventional 675-keV beam to 20.861 for FF rephasing (+51.2%).
4. **Synchronized boron-sheet timing is secondary in this model.** It raises exposure from 30.956 to 31.087 (+0.42%).
5. **The favorable result has a clear failure boundary.** In the widened 384-case sweep, the worst corner (50-keV stopping loss, 30% trapping, 15% spread, 50-keV jitter) falls to 0.546 mean resonance score and 0.539 mean 550-800 keV occupancy.
6. **The current reactor surrogate cannot represent this cleanly yet.** Its selected handoff already reports `proton_window_fraction = 1.0` at `proton_energy_center_keV = 120.0`, so adding a positive FF window term to that model would hide the actual kinetic question rather than answer it.

## Promotion gates for the next model

A PIC/stopping study should report, at minimum:

- trapped fraction per FF encounter
- energy spread after rephasing
- target-energy jitter / timing-to-energy error
- actual energy decrement and straggling through the proposed boron sheet
- electron heating introduced by the FF plasma channel
- laser/driver energy coupled into useful proton kinetic energy
- proton loss to walls / channel boundaries

The reactor-level model should only accept an FF case after those quantities are supplied explicitly.
