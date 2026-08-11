# Flying-Focus p-B11 Audit Status

Current canonical result:

**ISOTROPIC_ELECTRON_HOLE_RECIRCULATION_FAILS_POWER_GATE**

Chronology:

1. `results/` — repeated FF rephasing identified as the useful resonance mechanism.
2. `ignition_bridge/` — first energy bridge; retained for provenance.
3. `physical_channel/` — corrected the CM/lab target to ~638 keV and physicalized the boron column/stopping.
4. `power_flow/` — conserved p-B11/DT alpha power and identified a scalar-electron-drag closure window.
5. `distribution_kinetic/` — current result; replaces scalar `Te` with an explicit isotropic electron distribution and charges the e-e phase-space recirculation needed to maintain it.

The distribution-resolved result shows that a deep sub-keV electron hole can
indeed suppress fast-proton drag enough to close the alpha-supported proton
loop. However, maintaining that isotropic hole against electron-electron
relaxation costs orders of magnitude more phase-space recirculating power than
the local p-B11 fusion output.

Do **not** promote electron-hole shaping, `pB11_net_delta`, or ignition margin
from this branch.

The next credible gate is anisotropic/directed electron control or a full
Landau/Fokker-Planck calculation with an explicit wave operator. The repo's
isotropic scalar-Te shortcut is now superseded for this question.
