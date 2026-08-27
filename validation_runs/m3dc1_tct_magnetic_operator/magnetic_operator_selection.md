# Magnetic Operator Selection

## Result

Selected plasma-side operator for this rung:

```text
localized flux/vector-potential source in flux_nolin
```

Short-pulse classification:

```text
M3DC1_MAGNETIC_OPERATOR_SHEET_AUTHORITY_PASS
```

Sustained open-loop classification:

```text
M3DC1_MAGNETIC_OPERATOR_FAILS_SUSTAINED_CONTROL
```

The selected transfer sign is `minus`. In the short-pulse audit, `A=-0.01`
was the only sign with the immediate desired physical signature: sheet width
increased, peak `|Jphi|` decreased, and shoulder loading increased. The
zero-amplitude case was baseline-equivalent at the extracted times.

## Selection Boundary

This freezes one operator only for plasma-side evidence accounting. It does not
validate lithium current coupling, does not validate a boundary coil transfer
function, and does not justify closed-loop EARLY/AGGRESSIVE/HOLD control.

The sustained open-loop run over `0.0 <= t <= 0.25` did not maintain a wider
sheet. Its mean active width gain was
`-0.333598%`, the minimum
active width gain was `-0.867076%`,
and the maximum active peak-current change was
`0.361432%`.

Closed-loop handoff state:

```text
CLOSED_LOOP_HANDOFF_BLOCKED_BY_SUSTAINED_GATE
```

## Chain Kept Explicit

```text
commanded lithium current
  -> lithium/backing-conductor surface current K or J_Li
  -> local magnetic perturbation deltaB_control
  -> plasma magnetic boundary/edge perturbation
  -> current-sheet response
  -> topology/reconnection response
```

This rung only validates the middle plasma-side relation:

```text
deltaB_control proxy -> current-sheet response
```
