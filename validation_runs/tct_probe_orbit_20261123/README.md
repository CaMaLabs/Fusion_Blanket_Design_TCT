# Probe orbit, current-sheet replay, and reachable approach

This directory contains the completed orbit and local plasma experiments and the follow-on tests of coil-limited cross-sheet steering. The four archives preserve the original scripts, inputs, raw output and receipts. The extracted sources and summaries support inspection and reproduction from this branch.

## Shot rotation

Lyons et al. (2017), Eq. 1 and Fig. 2, fit an experimental toroidal E×B rotation profile for DIII-D shot 158103 at 3796 ms. Evaluating the fit and the archived EFIT together gives approximately 64.8 km/s at the 2.20 m probe reference and 44.3–80.0 km/s across the modeled corridor. The reference probe speed is 85.8 m/s. This compares the toroidal E×B component with the probe speed. Total local ion velocity and the actual current-sheet location require further data. [Rotation fit and shot identification](https://m3dc1.pppl.gov/Papers/lyons_PPCF_17.pdf)

At the reference height the fitted zero crossing is 39.5 mm outward from the orbit center and 14.5 mm beyond the corridor edge. Under the component-only speed comparison, a 0.21 m patch would pass in about 3.24 μs. The finest earlier local replay step corresponds to 6.37 μs under its assumed scaling. A shot-calibrated plasma run requires a verified flow vector, current-sheet location and compatible time and transport scales. The earlier four local flyby replays gave zero passing frames.

## Coil-limited approach

The steering target moves 2.084 mm inward along the flux normal with a quintic profile and then holds. It starts 40 ms after launch and commands a duration of 50, 100 or 200 ms. The angular-momentum reference interpolates between the estimated circular orbits at the two endpoints. The solver applies the same 1.6 kA limits, 100 Hz first-order lag and corridor as the archived orbit test. The inherited load is an imposed sensitivity. A tracking pass requires completing three laps, staying within 0.5 mm of the requested normal position 50 ms after the maneuver, and keeping the subsequent normal speed within 0.02 m/s.

All 48 original load-feedback runs completed three laps inside the corridor. Zero met the tracking gate at either integration resolution. The 24 finer cases ended 7.34–8.25 mm inward and had worst settling errors of 5.30–6.23 mm. This isolates the need to improve trajectory tracking before reusing a commanded path in the MHD model.

The 96 comparison runs also completed three laps inside the corridor. Neither removing the imposed drag nor feeding its exact modeled value to the controller met both tracking limits. The table shows the finest time step, with four starting angles and two directions at each duration.

| Load treatment | Tracking passes across 50, 100 and 200 ms | Worst post-settle position error across starting phases at 200 ms |
| --- | ---: | ---: |
| Imposed drag, feedback only | 0/24 | 5.85 mm |
| Imposed drag, exact feedforward | 0/24 | 5.04 mm |
| No drag | 0/24 | 1.02 mm |

The ideal linearized tangential I-coil authority at the reference orbit spans 0.000197 to 0.000410 T/m, with mean 0.000293 T/m. It covers the imposed nominal drag of 0.000400 T/m at 6 of 144 sampled angles, even when all available I-coil current is assigned to the tangential direction. This comparison uses the assumed load and the modeled vacuum coil response. The no-drag result also isolates a tracking error in the current controller. The current-sheet replay of a shot-calibrated, within-tolerance approach remains pending.

Run outputs are in [the drag comparison](orbit/runs/reachable_approach_comparison.json) and [the coil authority calculation](orbit/runs/coil_authority.json).

## Bounded approach and supplemental force

The new controller uses angular-momentum feedback, the exact modeled drag as feedforward, and bounded least-squares allocation across the 12 independent I-coils. Its highest-weight objective is the toroidal force. The first sweep tested three weight and gain settings. The main sweep covers three maneuver durations, four launch phases, both directions and two integration steps under zero, half and full imposed drag. The 1.6 kA channel limit comes from the triple-mode supply specification. The 100 Hz response, moment-to-mass ratio and quadratic drag are assumptions. [I-coil power supply specification](https://fusion.gat.com/pubs-ext/SOFT04/A24803.pdf)

In the controller screen at 200 ms, the selected weights and gains passed all four cases at half the imposed drag and missed all four at full drag. A separate replay-input sweep verified all four forward launch phases at half drag using 1,152 steps per lap and a coarser coil map. Its largest post-settle normal error was 0.122 mm. [Controller screen](orbit/runs/targeted_approach_screen.json) · [Replay inputs](orbit/runs/targeted_approach_replay.json)

All 144 runs with the selected controller completed three laps inside the modeled corridor. The table shows eight launch-phase and direction combinations per cell. The pass counts agreed at 576 and 1,152 steps per lap. At the finer step, the worst settled position error for the 200 ms move was 0.128 mm at half drag and 2.471 mm at full drag. [Installed coil runs](orbit/runs/targeted_approach_installed.json) · [Normal-force priority comparison](orbit/runs/targeted_approach_installed_normal_priority.json)

| Imposed drag | 50 ms move | 100 ms move | 200 ms move |
| --- | ---: | ---: | ---: |
| Zero | 0/8 | 8/8 | 8/8 |
| Half | 8/8 | 8/8 | 8/8 |
| Full | 0/8 | 0/8 | 0/8 |

At the displaced orbit, a linear program estimates the greatest toroidal force that can be produced while balancing radial centripetal acceleration and gravity at the target. For the imposed full drag it leaves a worst-phase shortfall of 0.000364 T/m forward and 0.000347 T/m in reverse over 144 phases. The force balance assumes instantaneous currents at every phase. The dynamic supplement is a virtual bidirectional tangential actuator with the same 100 Hz first-order lag. A real winding would need to deliver a phase-dependent force with compatible radial and vertical components. [Exact-trim calculation](orbit/runs/supplemental_authority.json)

For the 200 ms move at full imposed drag, ±0.00010 T/m of virtual authority passed 0/8 cases at each time step. ±0.00020 T/m passed 8/8 at each time step, with 0.126 mm worst settled position error and 0.00531 m/s worst settled normal speed. This is the lowest tested capacity that passed. The dynamic gate permits finite position and speed error, which accounts for the lower authority requirement than the exact circular trim calculation. At the modeled moment-to-mass ratio, ±0.00020 T/m corresponds to ±0.95 m/s² of tangential acceleration. [Supplemental actuator runs](orbit/runs/targeted_approach_supplemental.json)

## Plasma-frame pass

The follow-on local resistive MHD replay takes a computed trajectory that passed the 200 ms inward-move test at half assumed drag. It compares that trajectory with a matched no-core run on each of two grids and two fine-grid time steps. The sheet is either stationary in the vessel frame or assigned the fitted toroidal E×B velocity from the archived shot near the orbit. The transit time changes with relative speed. The 0.10 m length unit and 4.079 ms time unit stay fixed, and the commanded stand-off is 42 mm. The rotation fit measures a plasma-flow component. The sheet pattern speed, stand-off and transport remain model assumptions. The replay uses the spherical momentum-penalty mask with the probe self-field disabled.

The acceptance test requires above +0.020% FWHM across the full station set and at most +0.100% peak sampled sheet current after mesh, time-step and diagnostic allowances. The replay also follows the seeded X-line and O-line at entry, midpoint and exit. A continuation check tracks persistence of those lines. A census of new axes, a reconnection rate and energy deposited at the wall require additional diagnostics.

## Reproduce

Python 3 with NumPy, SciPy and Matplotlib is required. Run from this directory with the equilibrium path preserved in the checkout.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 orbit/shot_flow.py
python3 orbit/reachable_approach.py
python3 orbit/reachable_approach.py --comparison
python3 orbit/coil_authority.py
python3 orbit/targeted_approach.py screen
python3 orbit/targeted_approach.py installed
python3 orbit/targeted_approach.py installed --profile normal_priority
python3 orbit/supplemental_authority.py
python3 orbit/targeted_approach.py supplemental
python3 orbit/targeted_approach.py replay
python3 plasma/settled_pass.py replay
unzip -j archive/TCT_steered_current_sheet_replay.zip input/orbit_tracks.npz input/archive_mesh_hold.json -d plasma/input
```

See [the plasma replay instructions](plasma/README.md) for the matched no-probe runs and analysis. The archive contains the original per-frame outputs. The raw probe tracks can be regenerated using `python3 orbit/export_replay_tracks.py plasma/input`.
