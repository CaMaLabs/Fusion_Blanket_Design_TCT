# Lithium-To-Field Mapping Boundary

Classification:

```text
LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED
```

The M3D-C1 magnetic operator is a normalized localized flux/vector-potential
source. The short-pulse result establishes field-level reachability inside the
GEM reconnecting ROI, but it does not provide a calibrated transfer from
`mag_ctrl_amp` to physical tesla at a liquid-lithium surface.

Therefore the lithium bridge is limited to:

```text
IDEALIZED_MAGNETOSTATIC_TRANSFER_ONLY
```

For an ideal tangential sheet-current geometry:

```text
deltaB_t ~= mu0 K
K = deltaB_t / mu0
J_Li = K / d_conductor
```

where `K` is surface current density in A/m and `d_conductor` is the assumed
current-carrying lithium/backing-conductor thickness. This relation is not the
machine transfer function and does not include coil geometry, wall geometry,
shielding, plasma response, conductor returns, or time-dependent circuit limits.

Reference reactor-design sensitivity values used only where a dimensional
sensitivity is explicitly labeled:

| Quantity | Value | Source |
|---|---:|---|
| Background field at lithium proxy | 7.2 T | WINNING_CONFIGURATION_SUMMARY.md Candidate-0 values |
| Lithium velocity | 0.0022 km/s | WINNING_CONFIGURATION_SUMMARY.md Candidate-0 values |
| Current-path thickness proxy | 0.0014 m | WINNING_CONFIGURATION_SUMMARY.md Candidate-0 values |
| Trench/wetted width for sensitivity | 10.0 mm | lower edge of repository Fig. 7A plotted-width range |
| Wetted assumption | True | required by repository Eq. 23 gate |

The Ruzic/Fiflis gate uses total local field:

```text
B_Li,total = B_background_at_Li + deltaB_control_at_Li
```

The current repository evidence does not supply `deltaB_control_at_Li` for the
M3D-C1 operator, so no lithium operating point is declared as viable.

Claim boundary preserved:

```text
FIFLIS/RUZIC 2016 REDUCED SURFACE-RETENTION GATE
```

It is not a complete free-surface MHD simulation, reactor survivability
validation, or proof of lithium-current -> plasma coupling. The J-B orientation
correction uses `|J| |sin(theta_JB)|`; that is a repository adaptation, not part
of Eq. 22 as printed.
