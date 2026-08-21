# Actuator Definition

Chosen actuator: `scale_ext_field` in `C1input`.

Native source path: `/home/ubuntu/M3DC1-official/unstructured/rmp.f90`, where `scale_ext_field` multiplies RMP field components for `irmp=1`. Input registration is in `/home/ubuntu/M3DC1-official/unstructured/input.f90`.

Only controlled-case change:

```text
scale_ext_field = 0.8566360855
```

Mapping: `0.8566360855 = 1 - 0.14336391448782237`, directly from the high-resolution BOUT handoff peak-current reduction fraction. No amplitude sweep was run.

Spatial profile/location/width: inherited from official `RMP` files `rmp_coil.dat` and `rmp_current.dat`; no geometry was invented.

Start/ramp/duration: inherited from official one-step linear RMP response; no extra time dependence.

Sign-reversed falsification control: `scale_ext_field = -0.8566360855`.
