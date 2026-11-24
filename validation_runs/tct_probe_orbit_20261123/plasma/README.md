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

## Relative-speed and self-field sweep

The follow-on experiment reuses the passing, half-load orbit track and retains the 42 mm commanded stand-off, 23 mm sphere radius, 0.10 m length unit and 4.079 ms time unit. It compares the no-probe baseline, momentum-penalty core, imposed magnetic field, and combination. The field is a divergence-free guide-axis perturbation carried with the core. It uses the archived source geometry, width 0.19 and peak vector-potential coefficient 0.09 in normalized units. Its amplitude stays constant during the nominal pass. The startup sensitivity ramps the core penalty and field over 0.6125 ms. The model assumes the reference fluid is at rest in the sheet-pattern frame. The sweep tests relative-speed sensitivity under that assumption. Independent bulk flow, core heating and absolute magnetic protection remain unresolved.

The probe covers a 0.21 m patch or runs for at most 2.45 ms. The +10 m/s near-comoving case covers 24.5 mm and starts with the core already near the sheet. A transient within this window can depend on how the modeled interaction is initialized. The gate requires all 36 FWHM profiles, strictly above +0.020% widening and at most +0.100% increase in peak sampled plasma current. Refined comparisons deduct the diagnostic, mesh and time-step allowances from the width and add the mesh and time-step allowances to the peak current.

| Sheet and numerical setting | Solid core | Local field only | Core and field |
| --- | ---: | ---: | ---: |
| +10 m/s relative speed, coarse | 1/8 | 0/8 | 1/8 |
| +10 m/s relative speed, refined | 0/8 | 0/8 | 0/8 |
| +10 m/s relative speed, ramped and coarse | 2/8 | 0/8 | 2/8 |
| +10 m/s relative speed, ramped and refined | 0/8 | 0/8 | 0/8 |
| Stationary pattern, coarse and refined | 0/8 | 2/8 | 0/8 |
| −500, −5,000 and −64,683 m/s relative speed, coarse | 0/24 | 0/24 | 0/24 |

The table counts passing post-entry samples against the matched no-probe baseline. At +10 m/s and sudden startup, the solid-only 0.306 ms sample retained 35 of 36 common stations in the refinement. It showed +0.239% adjusted width and +0.074% adjusted peak current on that reduced support. Later samples exceeded the current cap. Ramping both inputs over 0.6125 ms restored full profile coverage at 0.306 ms. The adjusted widening there was +0.0067% for the core and +0.0019% for the combination, below the width threshold.

The stationary-pattern local field alone gave +0.0616% adjusted widening at 1.225 ms and +0.2001% at 2.450 ms. Adjusted peak current increased by +0.00210% and +0.00388%, respectively. The original elliptic and hyperbolic field lines remained trackable at all three topology samples. The qualified samples are isolated in time. Sustained widening, plasmoid breakup and delivery of the prescribed field with physical coils remain unverified.

Results are in the [relative-speed screen](runs/slip_screen.json), [refined comparison](runs/slip_refined.json), [ramped screen](runs/slip_startup_ramp_screen.json) and [refined ramped comparison](runs/slip_startup_ramp_refined.json).

Run from the parent of this directory.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 plasma/slip_sweep.py --output plasma/runs/slip_screen.json
python3 plasma/slip_sweep.py --refine --cases near_comoving stationary_pattern --output plasma/runs/slip_refined.json
python3 plasma/slip_sweep.py --cases near_comoving --ramp-s .0006125 --output plasma/runs/slip_startup_ramp_screen.json
python3 plasma/slip_sweep.py --refine --cases near_comoving --ramp-s .0006125 --output plasma/runs/slip_startup_ramp_refined.json
```

Use the same scratch `--cache` path across commands to reuse completed runs for identical inputs.

## Time-resolved field-only sweeps

The field-only follow-up uses the same local MHD model, orbit segment, 42 mm offset, physical units and width/current thresholds. It samples 24 post-entry times across the driven interval, three times the earlier cadence. A ported copy of the original annulus comparison retains the virtual sphere exclusion. The primary field-only comparison keeps all available current profiles and samples the peak over the local disk, including the center. The disk reaches 75 mm in the sheet plane and spans ±40 mm in the nominal normal direction. The peak uses the induced plasma current density in the sampled volume. The width metric remains the mean FWHM of the 36 fixed profile stations. The result also records the number of individual profiles that broaden by more than the mean-width gate.

The screen varies field amplitude by factors of 0.5 and 1.5, tests 40 m/s and 130 m/s relative speeds and reverses the nominal relative direction. It also tests a 0.6125 ms smooth entry and a pulse with 0.30625 ms rise and fall intervals. The latter reaches zero at patch exit and is followed by an unforced continuation. Refined comparisons use the same 64 × 52 × 52 and 80 × 64 × 64 meshes as the prior slip study, with two time steps on the finer mesh. Consecutive passing samples give the observed span and a flag when the final sample still passes.

The drive is a prescribed moving field in a periodic slab. The reference fluid is at rest in the assumed sheet frame and the model holds the earlier calibration assumptions. Field generation by hardware, the actual DIII-D pattern speed and independent bulk flow remain open.

The unmasked nominal case passed at 15 consecutive samples from 1.021 through 2.450 ms, a sampled span of 1.429 ms. Its adjusted width gain at the last sample was +0.2001% and its peak-current increase was +0.00388%. The same refined test at half amplitude passed at 14 consecutive samples and ended with +0.0966% width and +0.00192% peak current. The wider peak-sampling region retained the passes. Under the legacy comparison, the nominal gap between the two passing groups came from incomplete profile coverage under the virtual sphere exclusion.

The shaped pulse reached zero at 2.450 ms. In the initial refined run it remained above the width gate throughout the sampled 0.6125 ms field-off interval. At 3.0625 ms, it gave +0.2706% adjusted width and +0.00349% adjusted peak current. Twenty-three of 36 individual profiles exceeded +0.020% width at the finest setting. The original elliptic and hyperbolic field lines remained trackable.

The extended refined run passed at 40 consecutive samples from 0.919 through 4.900 ms. All 24 samples strictly after shutoff passed, and the latest sample was 2.450 ms after shutoff. At that sample, the mean width was +0.2451% and peak current was −0.0207% relative to the matched control, after the numerical allowances. Twenty-five of 36 stations individually exceeded +0.020% width on the finest run. Individual widths ranged from −0.547% to +0.996%. The seeded island and X-line persisted through the final topology check. The short and long pulse histories matched bit for bit over their shared interval at all three resolutions.

The coarse screen gave a qualifying interval at each tested strength, speed and turn-on setting. At 40 m/s the last passing sample was at 1.838 ms and the final mean width fell to −0.0528%. The other screened speeds passed through their final samples. Fine confirmation covered nominal amplitude, half amplitude, and the shaped pulse with both observation lengths.

Run from the parent of this directory.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 plasma/field_window.py --cache /tmp/tct-field-window --output plasma/runs/field_window_screen.json
python3 plasma/field_window.py --cache /tmp/tct-field-window --refine --cases nominal pulse_and_decay --output plasma/runs/field_window_refined.json
python3 plasma/field_window.py --cache /tmp/tct-field-window --refine --cases half_strength --output plasma/runs/field_window_half_strength_refined.json
python3 plasma/field_window.py --cache /tmp/tct-field-window --cases long_decay --output plasma/runs/field_window_long_decay_screen.json
python3 plasma/field_window.py --cache /tmp/tct-field-window --refine --cases long_decay --output plasma/runs/field_window_long_decay_refined.json
```

[Coarse screen](runs/field_window_screen.json) · [Nominal and pulsed refinement](runs/field_window_refined.json) · [Half-amplitude refinement](runs/field_window_half_strength_refined.json) · [Extended field-off screen](runs/field_window_long_decay_screen.json) · [Extended field-off refinement](runs/field_window_long_decay_refined.json)

## Initial guide-flow shear

The follow-up initializes the existing periodic slab with a divergence-free guide-direction velocity proportional to `sin(2y)`, where `y` is the normalized sheet-normal coordinate. The mean velocity and the velocity at the sheet center are zero. The signed control parameter is the guide velocity at +25 mm minus the guide velocity at −25 mm. The MHD solver evolves this initial flow with its existing viscosity and magnetic coupling. Each driven pulse is paired with an unforced case with the identical initial flow, numerical grid and time step.

The prescribed moving field, nominal amplitude, 42 mm stand-off and 0.30625 ms pulse edges are inherited from the extended field-off study. Shutoff occurs at 2.45 ms and the unforced continuation ends at 4.90 ms. The established unmasked mean width and local peak-current gates still apply. These initial guide shears represent a controlled sensitivity test in the local model. DIII-D bulk-flow and pattern-speed calibration remain open.

Use a positive sign when the initial guide velocity increases toward the field source. The two sides of the velocity profile are resolved on both meshes. With the field off throughout, the coarse guide-shear controls gave the same sampled sheet widths and peak currents as the zero-shear control to within numerical roundoff. The seeded island and its associated saddle are checked at four times in each refined run.

| Initial jump across 50 mm | Passing samples after shutoff | Final mean width change | Final peak-current change |
| ---: | ---: | ---: | ---: |
| −85 m/s | 14/24 | −0.573% | +0.199% |
| −55 m/s | 20/24 | +0.0418% | +0.0779% |
| −25 m/s | 24/24 | +0.159% | +0.0456% |
| 0 m/s | 24/24 | +0.245% | −0.0207% |
| +25 m/s | 24/24 | +0.0572% | +0.00900% |
| +55 m/s | 7/24 | −0.264% | +0.560% |
| +85 m/s | 0/24 | +1.327% | +2.182% |

These are the unmasked disk results after resolution and time-step allowances, measured against the matched unforced controls. The limits are above +0.020% mean width and at most +0.100% peak-current increase. At −55 m/s, the width cleared its gate at all 24 field-off samples. Four late current excursions broke the passing interval before the final two samples recovered. At +85 m/s, the finest grid gave +3.065% mean width and +1.175% peak current at the end. The adjusted peak exceeded the current limit at every field-off sample. The original elliptic axis and hyperbolic field line persisted in all seven modeled cases at the four topology checkpoints.

`field_window.py` defaults to zero initial flow. The zero-shear case in this sweep reproduced the prior refined extended run exactly.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 plasma/field_window.py --cases long_decay --shear-m-s 0 25 -25 85 -85 --cache /tmp/tct-guide-shear --output plasma/runs/field_guide_shear_screen.json
python3 plasma/field_window.py --refine --cases long_decay --shear-m-s 0 25 -25 85 -85 --cache /tmp/tct-guide-shear --output plasma/runs/field_guide_shear_refined.json
python3 plasma/field_window.py --cases long_decay --shear-m-s 55 -55 --cache /tmp/tct-guide-shear --output plasma/runs/field_guide_shear_intermediate_screen.json
python3 plasma/field_window.py --refine --cases long_decay --shear-m-s 55 -55 --cache /tmp/tct-guide-shear --output plasma/runs/field_guide_shear_intermediate_refined.json
```

[Coarse sweep](runs/field_guide_shear_screen.json) · [Coarse ±55 m/s runs](runs/field_guide_shear_intermediate_screen.json) · [Refined sweep](runs/field_guide_shear_refined.json) · [Refined ±55 m/s runs](runs/field_guide_shear_intermediate_refined.json)
