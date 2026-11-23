# TCT steered-orbit current-sheet replay

This experiment replays short sections of computed DIII-D probe trajectories in the normalized local resistive MHD model. The comparison tests the mechanical effect of the modeled motion on current-sheet width and peak sampled current.

## Results

All four flybys fell short of the width and peak-current criteria at all 49 sampled times after accounting for mesh and time-step sensitivity. Requiring only 27 common width stations gave zero passing samples as well. The one coarse pass occurred at normalized time 0.0375 in the farther flyby. Its nominal half-maximum width gain went from +0.2531% on the coarse run to +0.0386% on the first fine run and +0.0075% at the smallest step, below the +0.020% width threshold. The median central-half-current width change at that instant was −0.0052% on the finest run.

| Replay | Robust passing frames | Minimum peak-current increase at or after the kick, finest run |
| --- | ---: | ---: |
| Forward near | 0/49 | +528.3% |
| Reverse near | 0/49 | +529.7% |
| Forward far | 0/49 | +349.5% |
| Forward larger scale | 0/49 | +536.8% |

The vector-velocity implementation reproduced the archived brake-and-hold widths and peaks exactly at all 49 coarse sampling times.

## Next tests

Compare the orbit in the rest frame of the plasma near the sheet. Sweep the assumed local flow if shot-specific rotation is unavailable, and pair each mapped probe trajectory with the corresponding no-probe run. Then test a slower cross-sheet approach and brake within the achievable coil envelope while retaining toroidal motion.

A timescale check under the 0.10 m length mapping puts the archived 2.08 mm approach and brake in about 1.43 ms. The incremental normal acceleration from the modeled I-coils ranges from 1.66 to 3.23 m/s² at the reference orbit across 144 sampled angles, using a linearized force response and assigning all available current to that one direction. With a constant 3.23 m/s² in an ideal coil-only rest-to-rest maneuver, 2.08 mm takes about 51 ms. This estimate excludes ambient force and geometric coupling. A full orbital reachability calculation can incorporate those terms, bandwidth and concurrent steering demands.

## Trajectories and units

The source is the half-mass, fixed-moment probe with angular-momentum and vertical-priority steering, a 5% load increment, and same-area speed-scaled drag. For each direction, the case with the smallest recorded clearance under that load was selected. Those cases were reproduced at 576 steps per lap before exporting traces at 2,304 steps per lap. Both refined orbit trajectories completed three laps. The forward trace launches at 90° and the reverse trace at 270°.

The map unwraps toroidal angle as reference radius times phase displacement. It projects this distance and the radial and vertical offsets onto the local field direction, the outward flux normal, and the third orthogonal axis. The basis comes from DIII-D shot 158103 at 3796 ms evaluated at the reference position. The modeled current sheet is centered at local y = 0. The projected guide and in-plane positions are centered at the kick. The solid's projected displacement normal to the flux surface is added to the assumed stand-off. Hermite interpolation uses orbital position and velocity, with separate intervals on either side of the impulse to preserve the velocity change.

| Replay | Direction | Nominal stand-off | Assumed length unit | Implied sphere radius |
| --- | --- | ---: | ---: | ---: |
| Forward near | Forward | 0.42 | 0.10 m | 23 mm |
| Reverse near | Reverse | 0.42 | 0.10 m | 23 mm |
| Forward far | Forward | 0.55 | 0.10 m | 23 mm |
| Forward larger scale | Forward | 0.42 | 0.20 m | 46 mm |

The patch is approximately 0.21 m long at the 0.10 m scale and lasts approximately 2.45 ms in the orbit trace. The patch length and physical duration double in the larger-scale case. Every case covers normalized time 0 to 0.60, with the kick at 0.30. The length-scale case keeps the approximate normalized transit speed fixed. It changes the physical size represented by the normalization. These calibrations are sensitivity inputs. The physical current-sheet position, local time scale and probe size in DIII-D remain unverified.

## Plasma model and acceptance screen

The local model uses the same periodic double sheet, seeded island, relative velocity penalty, sphere and fluid initial condition as the earlier approach-and-hold replay. It prescribes all three components of the probe velocity. The core magnetic source is set to zero. This isolates kinematic forcing in a local domain. Establishing the trajectory with two-way plasma forces, calibrating normalized MHD parameters, and locating an actual current sheet along the chosen orbit require additional evidence.

The original annular peak-current scan is paired with the no-probe scan at the same time and locations. Each pair excludes points inside the sphere's smooth support. Width uses the original tracked sheet normal and compares common stations. The original screen requires all 36 width stations, mean half-maximum width increase above 0.020%, and peak-current increase at or below 0.100%. The 27-station diagnostic also reports frames that meet the numerical criteria with reduced station coverage. Saved diagnostics include the width containing the central half of positive current as a second width measure.

The coarse calculation uses a 64 × 52 × 52 grid with time step 0.00625. The fine grid uses 96 × 80 × 80. The larger archived time step was unstable for the faster flyby on that grid. The assessment compares the suitable runs with 0.003125 and 0.0015625 fine steps. Its margin combines sensitivity to the three settings and, for width, the manufactured-translation allowance. Spatial resolution and time step both change between the coarse and first fine settings. The resulting margins measure observed sensitivity across these runs.

## Reproduce

Run from the unpacked directory using Python 3, NumPy, SciPy and Matplotlib. The packaged track metadata records the archived and refined orbit inputs. The track exporter can also be copied into the unpacked probe recovery bundle to regenerate the two input files.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 steered_replay.py archive_mesh hold
for level in archive_mesh fine_half_step fine_quarter_step; do
  for case in baseline forward_near reverse_near forward_far forward_large_scale; do
    python3 steered_replay.py "$level" "$case"
  done
done
python3 assess_replay.py --archive input
```

`input/archive_mesh_hold.json` supplies the reference for the hold replay check. The probe recovery bundle contains the orbit code and coil-model inputs.

- [Steering and orbit inputs](https://chatgpt.com/library?file_id=libfile_a784eedf42208191ae687259d5ebb80d&account_id=personal)
- [Original approach-and-hold reference](https://chatgpt.com/library?file_id=libfile_d6bf28a0ef448191bee6078ef42d11d9&account_id=personal)
