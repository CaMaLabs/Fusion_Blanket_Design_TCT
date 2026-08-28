# Magnetic short-pulse discrepancy audit

Authoritative reference: branch `agent/tct-mechanism-explorer` at
`3947de294b9f8eb9cb4d37d00b5cc34220b62fa3`.

## Finding

The archived manual PASS and the four explorer timing seeds were not the same
physical case. The manual `minus_C1input` used amplitude -0.01,
`t_on=0.0`, `t_off=0.05`, zero ramp, `ntimemax=2`, `ntimepr=1`, and
`dt=0.05`. Its favorable sample was `t=0.10`, after turnoff: width increased
by 0.0117982301091768 (0.5514%) and Jpk decreased by 0.003602 (-0.3768%)
against the equal-time baseline. The explorer's earliest seed was
`0.05 -> 0.10`, a state-shifted pulse rather than a reproduction.

The explorer also included the command-on output in its active mean and ended
impulse scoring at turnoff. This can dilute or miss a post-turnoff response.
It paired output rows by list index without explicitly verifying equal physical
time.

Baseline and executable paths, amplitude, geometry, ramp, ROI, width/Jpk
definitions, center/shoulder regions, and output cadence match in the repository
evidence. Both width extractors use 2.354820045 times the square root of the
jphi-weighted Z variance. The repository records executable paths but not the
binary hash or patched-source hash; live patch identity remains unresolved.

## Corrective change

Impulse scoring now aligns equal-time samples, excludes the command-on sample,
includes a configurable post-turnoff horizon, and records immediate/peak
response, latency, duration, integral, and sign reversal. Width, Jpk, high-J,
and center/shoulder changes are evaluated at the same peak-favorable sample.
Long-window mean remains a sustained metric. A frozen `0.0 -> 0.05` seed is
restored before the timing-map seeds.

Evolution remains paused until the frozen case is rerun in the native
`/home/ubuntu/M3DC1-official` environment and reproduces the archived PASS
through the explorer.
