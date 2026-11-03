# Anisotropic / Directed Electron Kinetic Audit — 2026-08-11

## Classification

**DIRECTED_ELECTRON_TWO_STREAM_FAILS_RECIRCULATION_AND_STABILITY_GATE**

This audit tests whether directional electron phase-space control can reduce field-parallel drag on the frame-corrected `638 keV` proton packet without the isotropic-hole refill penalty. It keeps `n_fast = 0.20 ne`, so quasineutrality gives `5 nB/ne = 0.80`.

Three cases are separated.

### Symmetric magnetic mirror / loss cone

A symmetric trapped-electron loss cone does **not** reduce the parallel drag in the Rosenbluth friction-kernel screen. Every tested mirror ratio from `1.2` to `100` gives drag above the Maxwellian baseline; the least-bad case is still about **1.047x** baseline. Magnetic trapping should therefore not be credited as a generic proton-stopping suppression factor.

### Current-neutral return current

The fast-proton current requires a mean electron particle drift of `+0.20 vp` if boron is stationary. That current-neutral shifted Maxwellian lowers electron drag only to **0.804x** baseline. Collision burden remains **8.215 P_fusion**, useful proton demand is **8.289 P_fusion**, and the alpha-supported proton loop does not close. The parallel Spitzer maintenance screen is about **8.10 P_fusion**.

### Current-neutral skewed two-stream electrons

A strongly skewed distribution can close the proton loop. The lowest recovery-requirement closed case has:

- 92% of electrons at `+1.20 vp`;
- 8% at `-11.30 vp` (`0.417 c`);
- relative stream speed `1.80 v_te`;
- electron drag factor **0.0272**;
- collision burden **1.100 P_fusion**;
- useful proton demand **1.173 P_fusion**;
- direct-electric stream left **0.605 P_fusion**.

The directional drag physics therefore works, but maintaining the counterstream fails the power gate. Classical e-e momentum relaxation costs about **228.8 P_fusion**, or **229.0 P_fusion** including the prior proton self-shape lower bound. The remaining direct-electric stream would require **99.736% phase-space energy recovery** to pay that burden before other plant loads.

The lowest raw stream-maintenance closed case is still about **197.4 P_fusion** and requires **99.844% recovery**. Both loop-closing points have relative electron-stream drift above the electron thermal speed and are flagged as electrostatic/beam-instability-risk cases.

## Decision

Do **not** promote directed electron two-stream drag cancellation into `m3dc1_tct_hybrid_bridge.py`.

The surviving flying-focus program is now the part that has repeatedly survived falsification: the ~638-keV proton rate-lock target, low-material-intersection racetrack, physical tens-of-eV per-effective-pass stopping scale, alpha-to-proton return, FF phase recovery, orbit residence, TCT confinement, and direct conversion. Further reactor optimization should maximize reaction probability and recoverable charged-particle power **per unit of unavoidable electron drag**, rather than spending large recirculating power trying to erase that drag.
