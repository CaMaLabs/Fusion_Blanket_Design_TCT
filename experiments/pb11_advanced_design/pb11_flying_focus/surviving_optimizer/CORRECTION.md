# Stage-7 Compression Interpretation Correction

The `surviving_optimizer` numerical sweep is retained for provenance, but its interpretation of `volume_compression_factor = 0.074` as a physical remaining-volume fraction is superseded by Stage 8.

Inspection of `m3dc1_tct_hybrid_bridge.py` shows that `volume_compression_factor` is a bounded actuator/proxy magnitude computed from the dynamic-compression setting, timing, and duty. It is **not** `V/V0`. Therefore `1/0.074 ~= 13.5x` density and the associated `~0.76 s` burn-target residence are not supported by the repository semantics.

Stage 8 uses the separate explicit `compression_amplitude_pct = 10%` only as a bounded geometric sensitivity, corresponding to roughly `1.23–1.37x` particle-conserving density and `~8.35–7.52 s` inherited burn-target residence.

All Stage-7 reaction/drag optimization results remain useful; only the physical compression/dwell interpretation is superseded.
