# Tungsten-encapsulated compressed titanium beryllide vs be_outer_killer

Status: **experiment specified; no new neutron-transport or thermal-mechanical results claimed**.

## Origin and reference
Proposal: compressed Be–Ti powder contained in tungsten modules, compared on identical geometry to the frozen `be_outer_killer` Reference Design V1. The core must be represented as either a physical Be+Ti powder blend or as pre-reacted TiBe12 powder: **these are not equivalent materials**. Do not equate compression with formation of the intermetallic phase.

Frozen reference: Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be; splits 0.15/0.20/0.40/0.15/0.10, liquid Li wall kept fixed. Keep total thickness, enrichment, source, coolant, geometry and thermal loading identical across cases. Preserve the baseline, do not overwrite it.

Existing `scripts/run_openmc_ordering_ab_fast.py` includes `ti_sandwich` with Be12Ti but **does not resolve a tungsten shell and compacted powder voids**. Its `fusion_engine_v5.engine.reactor_simulation` call is not sufficient evidence of a full particle-transport model.

## Cases
- A: exactly frozen baseline, original W-Ti-B4C layer intact.
- B: homogeneous TiBe12 replacing layer 4 (no W shell), same total thickness.
- C: tungsten-faced/canned TiBe12 powder in layer 4, independent tungsten shell thickness, porosity, gap and optional helium purge. Reflect displaced active material.
- D: tungsten-faced/canned physically blended Be+Ti powder in layer 4, with phase fractions separate from case C.
- E: TiBe12 segmented pellets with W-facing armor and non-tungsten structural containment (control for the tungsten penalty).
- F: retain original layer 4 and replace outer layer 5 with tungsten-canned TiBe12 (placement sensitivity).

## Parameter sweep
Shell thickness on each radial face: 0, 0.5, 1, 2, 5 mm. Packing fraction: 0.65, 0.80, 0.90, 0.98. Optional gap: 0, 0.25, 1 mm. Run matched total radial envelope and matched source. On outer/inner shell faces and side walls, account for real 3-D coverage, not only radial slab fractions. Include thermal-stress relief/segmentation as a separate dimension.

The stoichiometric TiBe12 (Be12Ti) mass fractions from atomic masses 9.0121831 and 47.867 are Be ~69.34 wt% and Ti ~30.66 wt%. Its neutron-multiplier response must be taken from nuclear data, not guessed from the Be mass fraction. W absorption/scattering and secondary reactions likewise require transport.

## Outputs and gates
1. OpenMC with declared cross sections and transport settings: TBR (with confidence interval), neutron leakage, energy-dependent current, neutron multiplication, heating (W/core/breeder), dpa and He/H generation proxies where physically supported.
2. Thermal-mechanical model: `T_max`, gradient, contact conductance sensitivity, pressure/creep/stress, irradiation swelling and void accommodation, cyclic fatigue, He/T transport and inventory.
3. Engineering: retained Li2O breeding volume, total mass, activated inventory, cooling routing, compatibility of W with Be/Ti at contact, manufacture and remote maintenance.
4. Compare paired seeds and particles; independent replications, uncertainty intervals; reject if worsening TBR or safety margins exceeds preset tolerance.
5. Keep TCT control fixed for the blanket comparison; do not attribute neutron effects to M3D-C1 plasma-control validation.

## Literature leads
- Industrial TiBe12 via powder metallurgy: DOI 10.1016/j.fusengdes.2020.111862
- TiBe12 segmentation thermal-cycle study (2026): DOI 10.1016/j.nme.2026.102171
- High-dose irradiated thermal conductivity: DOI 10.1016/j.jnucmat.2021.153430
- Fusion multiplier review: DOI 10.1016/j.fusengdes.2008.11.009

## Falsification criterion
If the shell consumes too much multiplication volume, worsens TBR, thermal gradients, or swelling stress versus the frozen baseline, reject the concept or move the W armor to the exposed face only. A screening/proxy score is not an OpenMC result.
