# FAIR-MAST Review Checklist

## Event Labels

- [ ] D-alpha accepted `true_elm` rows are plausible ELM/event labels.
- [ ] Ambiguous rows are correctly excluded from primary metrics.
- [ ] Any artifact-like rows are identified and documented.
- [ ] Close split peaks are handled consistently.
- [ ] Analysis-window edge events are handled conservatively.

## Trigger Timing

- [ ] Trigger line precedes D-alpha event, not just event onset.
- [ ] Trigger lead is physically meaningful for each accepted case.
- [ ] Sub-1 ms and duplicate-trigger rows are not counted as robust successes.
- [ ] False-trigger handling is reasonable.
- [ ] The `0.5-15 ms` association window is defensible.
- [ ] Multi-diagnostic fusion gain is interpreted as marginal, not decisive.

## Null Test

- [ ] Per-shot circular time-shift null is a fair chance-alignment control.
- [ ] Preserving trigger count per shot is sufficient for the first null test.
- [ ] Additional stricter nulls are identified if needed.
- [ ] Reported p-values are interpreted as timing-specificity evidence only.

## Control Interpretation

- [ ] `5-8 ms` lead is plausibly useful only for bounded adjustment, not full
      late-stage event prevention.
- [ ] Results support preventative/moderate control direction, not causal TCT
      validation.
- [ ] Reviewer agrees with stated claim boundaries.

## Requested Outcome

- [ ] Accept packet as credible preliminary experimental precursor evidence.
- [ ] Request changes to labeling rules.
- [ ] Request additional diagnostics.
- [ ] Reject precursor interpretation.

Reviewer notes:

```text

```
