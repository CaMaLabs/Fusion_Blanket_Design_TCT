# Proposed State-Dependent Controller

Classification:

```text
M3DC1_MAGNETIC_RESPONSE_SIGN_REVERSAL
```

This is a paper controller implication only. No closed-loop controller was run.

The tested command was fixed at `A=-0.01` with `duration=0.05`, `ramp=0`, and
the frozen magnetic ROI. High-resolution timing shows a transient broadening
lobe followed by decay or sign reversal in every tested window. Use the
favorable lobe as a transient intervention candidate and avoid holding the same
command continuously.

Recommended logic from this audit:

```text
EARLY: tested negative magnetic pulse can be used only as a timed transient.
AGGRESSIVE: unresolved; do not increase amplitude until the Jpk conflict is resolved.
HOLD: zero or reduced control after the favorable lobe decays; continuous fixed bias is not supported by current evidence.
```

Amplitude selection beyond `A=-0.01` remains unresolved.
