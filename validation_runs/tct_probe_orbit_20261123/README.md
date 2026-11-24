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

| Sheet pattern assumption | Time across the patch | Frames passing both gates | Finest-run behavior |
| --- | ---: | ---: | --- |
| Stationary in vessel frame | 2.450 ms | 0/13 | Every post-entry frame exceeded the peak-current cap and had fewer than 36 valid FWHM stations. The guide field changed sign in the domain by midpoint, so the one-turn field-line map could not classify the original lines there or at exit. |
| Follows the fitted toroidal E×B component | 3.247 µs | 0/13 | The mean FWHM narrowed by 0.404% at exit across all 36 stations. The original elliptic and hyperbolic field lines were tracked at all three topology samples. |

The first stationary fine-grid time step overflowed. The stationary comparison in the receipt uses the stable 240- and 480-step integrations on the fine mesh. Both replays are local sensitivity tests at one stand-off and one reachable trajectory. The supplemental actuator result establishes a force target for steering. The replay leaves the widening and breakup goals unmet. [Matched plasma replay](plasma/runs/settled_pass_replay.json)

## Pattern-speed diagnostic

The public analysis of DIII-D shot 158103 at 3796 ms provides a toroidal E×B flow fit and describes the applied n=2 RMP. A search of the public shot literature and the repository inputs did not locate a phase trace or a signed frequency for a specific island or current-sheet pattern at this time. The public Fusion Equilibrium Challenge release omits machine shot identifiers and lists coil currents as its magnetic inputs. Access to unpublished shot signals follows the DIII-D user agreement. [Shot analysis](https://m3dc1.pppl.gov/Papers/lyons_PPCF_17.pdf) · [Public benchmark schema](https://fusion-equilibrium-challenge.sophelio.io/data/) · [DIII-D user agreements](https://d3dfusion.org/user-agreements/)

The orbit speed is 85.70 m/s at 2.198 m. A toroidally traveling mode within ±10 m/s of the probe has signed frequency divided by toroidal mode number in the range 5.48 to 6.93 Hz in the orbit sign convention. Establishing a target requires an identified mode, its signed phase rate, a radial localization consistent with the target and a separate estimate of local fluid velocity. The existing single magnetic precursor channel request can be extended to synchronous calibrated toroidally separated probes at compatible poloidal locations, their geometry and sign conventions, the applied coil traces or pickup-corrected data, and ECE or another radial diagnostic. The near-frequency band calls for a coherent interval around 3.796 s long enough to resolve it. A stationary feature requires a DC-sensitive diagnostic. [Precursor diagnostic request](../diiid_diagnostic_reconstruction_default/DIIID_LIMITED_DATA_ACCESS_REQUEST.md) · [DIII-D rotating island measurements](https://link.aps.org/accepted/10.1103/PhysRevLett.132.065107)

`orbit/mode_pattern_speed.py` fits the chosen toroidal harmonic alongside other specified harmonics. Its input is an NPZ with `time_s`, `phi_rad` and `signal[time, probe]`. Supply calibrated synchronous samples, remove direct coil pickup and use the orbit's toroidal sign convention. The fit reports signed frequency, speed at the specified radius, interval, cycle coverage and phase residual. Synthetic forward and reverse tracks verified the sign and scale of the estimator. Shot-specific speed remains unmeasured in these runs.

```sh
python3 orbit/mode_pattern_speed.py magnetic_diagnostics.npz --mode 1 --max-mode 2 --radius 2.198
```

The slip and self-field replay uses prescribed pattern speeds as sensitivity inputs. In the stationary-pattern model the moving local field alone cleared the refined width and peak-current gates at two of eight post-entry samples. The solid core and the core with the field missed the refined gate, including in the near-comoving startup comparison. [Slip and self-field replay](plasma/README.md#relative-speed-and-self-field-sweep)

The denser field-only follow-up measured a nominal span of 1.429 ms across 15 consecutive passing samples with the virtual sphere exclusion removed. A shaped pulse remained above the width gate at all 24 samples in the 2.450 ms field-off interval on the extended refined run. The final mean width increased by 0.2451%, peak sampled current fell by 0.0207%, and the original island persisted in the periodic model. [Time-resolved field-only sweep](plasma/README.md#time-resolved-field-only-sweeps)

The same pulse retained all 24 field-off passes at initial guide-velocity jumps of ±25 m/s across 50 mm. At −55, +55, −85 and +85 m/s it passed 20, 7, 14 and 0 samples respectively after refinement. The effect depends on the magnitude and direction of the initial shear in the local model. [Guide-flow shear sweep](plasma/README.md#initial-guide-flow-shear)

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
