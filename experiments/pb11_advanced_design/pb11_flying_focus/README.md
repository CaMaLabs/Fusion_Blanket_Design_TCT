# p-B11 Flying-Focus Resonance Audit

This directory adds a standalone screening audit for applying flying-focus (FF) proton acceleration/rephasing to the advanced p-B11 branch. It is intentionally separate from `m3dc1_tct_hybrid_bridge.py` because the current surrogate already saturates `proton_window_fraction` at 1.0 for the selected 120-keV case, so adding a simple FF bonus there would not be informative.

## What this audit tests

The audit asks a narrower question:

> Can a programmable FF proton injector/rephaser keep a nonthermal proton packet near the broad ~675-keV p-B11 resonance more effectively, per delivered proton energy, than the present 120-keV hold or a one-shot 675-keV beam?

It does **not** predict ignition, reactor gain, an absolute fusion rate, stopping power, or MHD stability.

## Literature anchors

- Z. Gong, S. Cao, J. P. Palastro, and M. R. Edwards, "Laser wakefield acceleration of ions with a transverse flying focus," *Physical Review Letters* **133**, 265002 (2024), DOI: `10.1103/PhysRevLett.133.265002`, arXiv: `2405.02690`. The published 3-D PIC case produced a 1.6-GeV proton beam with 3.7% relative energy spread; this audit uses **3.7% only as an optimistic spread anchor**, not as a demonstrated result at 675 keV.
- E. Gerstmayr et al., "Experimental demonstration of Flying-Focus enhanced Thomson scattering," arXiv: `2607.15805` (2026). This is used as an experimental anchor for matching a programmable focal trajectory to a particle trajectory over an extended interaction.
- V. F. Dmitriev, "Alpha-particle spectrum in the reaction p + 11B -> 3 alpha," arXiv: `0812.2538`, discussing the 675-keV proton resonance.
- Modern p-B11 work continues to emphasize the importance of fast/nonthermal proton populations and alpha handling; see I. E. Ochs et al., *Physical Review E* **106**, 055215 (2022), DOI: `10.1103/PhysRevE.106.055215`.

## Model

`pb11_flying_focus_audit.py` tracks proton energy packets over repeated idealized boron-sheet encounters. Each encounter applies a configurable stopping-energy decrement and straggling. FF cases may rephase a configurable fraction of the packet back toward 675 keV with configurable spread and target jitter.

The nuclear response is a **normalized two-resonance proxy**, not an evaluated cross-section table. It preserves a broad primary feature around 675 keV and a smaller low-energy feature near 148 keV so the existing 120-keV repository operating point is not artificially scored as zero.

Nominal run:

```bash
python pb11_flying_focus_audit.py --output-dir results
```

Default nominal assumptions:

- 120,000 macro-particles
- 32 reaction-sheet encounters
- 20 keV stopping decrement per encounter
- 4 keV straggling
- FF injector spread: 3.7%
- FF rephase trapping: 85%
- synchronized FF + sheet trapping: 92%
- explicit 384-case falsification sweep over stopping loss, trapping, spread, and jitter

## Nominal results

| Case | Mean resonance score | Mean 550-800 keV occupancy | Exposure vs one-shot 675 keV | Exposure / delivered MeV |
|---|---:|---:|---:|---:|
| 120-keV autoresonant hold | 0.2132 | 0.0000 | 0.733x | 8.789 |
| conventional 675-keV injection | 0.2909 | 0.2113 | 1.000x | 13.793 |
| FF 675-keV injection only | 0.2944 | 0.2117 | 1.012x | 13.956 |
| FF 675-keV rephase | 0.9674 | 0.9999 | 3.325x | 20.861 |
| FF rephase + synchronized sheet | 0.9715 | 1.0000 | 3.339x | 20.977 |

The main result is that **narrower FF injection alone does almost nothing once stopping drift dominates**. The large effect comes from repeated rephasing. In the nominal case, FF rephasing keeps the packet in the 550-800 keV window for all 32 modeled encounters and raises cumulative resonance exposure by ~3.33x versus a one-shot 675-keV beam.

The synchronized boron-sheet case adds only ~0.4% cumulative exposure over ordinary FF rephasing under the nominal assumptions. That means the first hardware/physics priority should be the rephaser itself; sheet synchronization is a second-order optimization unless a higher-fidelity model shows a stronger transport benefit.

## Falsification sweep

The sensitivity grid spans:

- stopping decrement: 10, 20, 35, 50 keV/encounter
- FF trapped fraction: 0.30-0.95
- FF energy spread: 3.7-15%
- target jitter: 0-50 keV

Of 384 cases:

- 255 (66.4%) passed the strong gate: mean resonance score >= 0.75 and mean primary-window occupancy >= 0.75
- 379 (98.7%) passed the acceptable gate: both metrics >= 0.60
- worst case: 50-keV loss, 30% trapping, 15% spread, 50-keV jitter -> resonance score 0.546 and window occupancy 0.539
- best case: 10-keV loss, 95% trapping, 3.7% spread, zero target jitter -> resonance score 0.974 and window occupancy 1.000

So the concept is **not unconditionally favorable**. It breaks down when trapping is poor at the same time that stopping, spread, and target jitter are all large.

## Driver-efficiency result

The nominal synchronized FF case has 20.977 normalized resonance-exposure units per delivered proton MeV versus 13.793 for conventional 675-keV injection. Therefore, within this model, FF only needs an optical-to-proton efficiency of about **65.8% of the conventional driver's proton-energy efficiency** to match it on resonance exposure per source-energy input.

Example: if a conventional injector were 20% efficient from source energy to proton kinetic energy, the FF path would need about 13.2% optical-to-proton efficiency to match its normalized resonance-exposure efficiency. This is a **relative screening threshold**, not a measured laser-system efficiency claim.

## Files

- `pb11_flying_focus_audit.py` - standalone reproducible audit
- `results/case_summary.csv` - nominal five-case comparison
- `results/cycle_history.csv` - per-cycle resonance score and window occupancy
- `results/sensitivity.csv` - 384-case falsification sweep
- `results/driver_efficiency_thresholds.csv` - relative FF efficiency thresholds
- `results/optical_efficiency_sensitivity.csv` - source-energy sensitivity for the nominal synchronized FF case
- `results/summary.json` - machine-readable audit summary and guardrails

## Interpretation / next physics step

This audit justifies promoting FF rephasing to a higher-fidelity kinetic study. The next useful step is **not** to increase the surrogate `pB11_net_delta` directly. It is to replace the assumed stopping decrement and trapping fraction with values from a low-energy PIC/stopping calculation for the actual proton channel and boron-sheet density, then hand only surviving operating points back into the reactor-level surrogate.
