# TCT research-loop audit — 2026-10-25

Research lead Chase Lunsford / CaMaLabs; AI-assisted workflow audit.

## Observed handoff state

The research branch is agent/tct-pulse-train-audit, not main. At inspection it contains 115 job manifests and 115 machine receipts. Eleven receipts (101–111) lack formal assistant acknowledgements. Some have existing successors, so missing acknowledgements must not be interpreted as unperformed science. Both supervisor task variants were paused. The canonical supervisor has been resumed and assigned backlog reconciliation; the old duplicate remains paused. Intake remains separate and defers science-job creation while that backlog exists.

## Current evidence boundaries

- 103: TOKAMARK_BOUNDED_CHUNK_INCOMPLETE, first-chunk time/signal mismatch for two channels; no event analysis or precursor support.
- 104: M3DC1_TCT_NATIVE_PRECURSOR_CONTROLLER_TIMESCALE_WINDOW_MISMATCH. Physical timing prevents the intended interpretation; do not silently rescale actuator times.
- 105 failed at pipeline level and already has repair successor106.
- 106: M3DC1_NATIVE_FEEDBACK_CONTROLLER_NO_AUTHORITY_FOUND. A native controller audit ran; it did not establish control authority.
- 107 ingested 64 DIII-D dataset rows. Dataset row is not an original machine discharge number.
- 108: EFIT_SHOT_FRAME_VERIFIED_NATIVE_HANDOFF_NOT_YET_VALIDATED; no validated shot-to-native equilibrium/profile mapping.
- 109: REAL_SHOT_VACUUM_PF_COUNTERFACTUAL_COMPLETED. +/-1% F1A perturbation yields max vacuum delta-psi about 0.13005% of measured psi span. Frozen plasma, no self-consistent plasma response or TCT stabilization conclusion.
- 110 access failure already has repair successor111.
- 111: GOLEM_51929_EXPERIMENTAL_WAVEFORM_ACCESS_VERIFIED. Units/time reference remain unverified, and shot51926 plasma-current file is unavailable. It is an observational H-fuel/no-plasma analog, not an ELM/Mirnov or causal TCT demonstration.

## Optimized progression

1. Read the oldest missing acknowledgement, its manifest, summary and relevant log, then inspect all successors. Backfill one precise receipt per supervisor invocation without creating duplicate successor jobs. Acknowledgement must record classification, source receipt/hash, fuel track, existing successor, quantitative finding and claim boundary.
2. Maintain separate intake, observational timing, vacuum actuator, reduced model, native solver and causal intervention evidence. A result from one level does not promote the others.
3. Use one outstanding focused successor per lineage. Repeated unchanged source inventories/status queries are blocker monitoring, not experiments.
4. After reconciliation, target the prerequisite that blocks the scientific question: units/clock for GOLEM, chunk dimension alignment for TokaMark, or validated equilibrium/profile handoff and actuator authority for native M3D-C1. Prefer a falsifiable intervention/control comparison over another unrelated source acquisition when its inputs are ready.
5. Preserve frozen width gain >+0.020% and Jpk change <=+0.10%, zero/handoff equivalence, formal classification strings and all p-B11 fidelity separations.
6. Record successes and informative negative results before queuing successors. Never interpret no-authority, timing mismatch, or failed handoff as infrastructure success merely because return_code=0.
7. Use Git receipts to verify completed work; check host deployment/version/space separately. No Ubuntu service state has been directly verified in this audit.

The worker already has locking, local-result republishing, ambiguous-push verification and size-bounded artifact selection. Preserve those mechanisms. The highest-value repair here is supervisor/handoff reconciliation, not another worker rewrite.

Google Drive's March threshold bundle and DT_TCT_v8 report are historical reduced-model context. The latter documents flat trigger sensitivity and unimplemented latency/horizon terms. They must not override current branch receipts or establish present causal/physical validation.
