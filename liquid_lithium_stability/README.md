# Liquid Lithium Surface Stability

This module contains the lightweight reduced-model layer for liquid-lithium
surface-stability prioritization.

Main entry point:

```bash
python scripts/run_liquid_lithium_stability.py \
  --run-dir validation_runs/liquid_lithium_stability_default \
  --check
```

Primary outputs:

- `validation_runs/liquid_lithium_stability_default/liquid_lithium_stability_results.csv`
- `validation_runs/liquid_lithium_stability_default/liquid_lithium_stability_summary.json`
- `validation_runs/liquid_lithium_stability_default/LIQUID_LITHIUM_STABILITY_REPORT.md`

## Fiflis/Ruzic 2016 surface-retention gate

The repository also includes an experimentally anchored screening gate based on
Fiflis et al., *Nuclear Fusion* 56 (2016) 106020, Eq. 20 and Eq. 22-23. It
screens liquid-surface retention against current density, magnetic field,
tangential plasma velocity, trench width, wetting state, and J-B orientation.

Run the paper-anchored sweep directly:

```bash
python3 scripts/run_ruzic_li_surface_gate.py --check
```

For the current A/D validation-gap audit on Ubuntu, run from the repository root:

```bash
bash run_ubuntu_ad_audit.sh
```

The launcher always runs the Ruzic gate and its pytest checks. If the `openmc`
executable is installed, it also invokes the repository's existing OpenMC
`be_outer_kill` ordering study and records the result. Outputs are written under
`validation_runs/ubuntu_ad_audit_default/` by default.

Important boundaries:

- The J-B angle correction uses the magnitude of `J x B` as a repository
  adaptation; it is not part of the printed Eq. 22 fit.
- Eq. 22-23 constrain liquid-surface retention/ejection; they do not supply a
  measured lithium-current to plasma-edge actuator transfer function.
- The current OpenMC geometry remains a simplified cylindrical stack and the
  Ubuntu audit does not relabel it as an engineering-complete blanket model.

Literature synthesis:

- `LIQUID_LITHIUM_STABILIZATION_LITERATURE.md`

Claim boundary:

This is a deterministic reduced-model scenario matrix plus an experimentally
anchored surface-retention screening gate. It is not reactor validation, not a
full free-surface MHD solution, not liquid-lithium material compatibility
validation, and not proof that TCT or lithium-current coupling works.
