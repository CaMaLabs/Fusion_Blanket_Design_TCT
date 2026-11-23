# Probe orbit, current-sheet replay, and reachable approach

This directory contains the completed orbit and local plasma experiments and the follow-on test of coil-limited cross-sheet steering. The four archives preserve the original scripts, inputs, raw output and receipts. The extracted sources and summaries support inspection and reproduction from this branch.

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

## Reproduce

Python 3 with NumPy, SciPy and Matplotlib is required. Run from this directory with the equilibrium path preserved in the checkout.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 orbit/shot_flow.py
python3 orbit/reachable_approach.py
python3 orbit/reachable_approach.py --comparison
python3 orbit/coil_authority.py
unzip -j archive/TCT_steered_current_sheet_replay.zip input/orbit_tracks.npz input/archive_mesh_hold.json -d plasma/input
```

See [the plasma replay instructions](plasma/README.md) for the matched no-probe runs and analysis. The archive contains the original per-frame outputs. The raw probe tracks can be regenerated using `python3 orbit/export_replay_tracks.py plasma/input`.
