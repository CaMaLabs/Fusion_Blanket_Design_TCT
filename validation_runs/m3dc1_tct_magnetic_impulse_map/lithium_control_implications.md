# Lithium Control Implications

Classification:

```text
LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED
```

The timing map does not provide a physical calibration from normalized
`mag_ctrl_amp` to `deltaB [T]`, surface current `K [A/m]`, or lithium volumetric
current density `J_Li [A/m^2]`. Normalized M3D-C1 amplitudes were not inserted
into the Fiflis/Ruzic equations.

If magnetic control gain changes with state, a purely DC lithium bias cannot
represent the full timing-dependent controller. A later architecture may need:

```text
modest lithium standing bias
+ fast modulated lithium/backing-conductor/trim-field correction
```

That remains a hypothesis until dimensional magnetic transfer is calibrated.
