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
- [ ] SXR gains are checked for event-signature leakage before being treated as
      operational precursors.
- [ ] Completed SXR morphology-gate result is treated as negative for this
      simple gate family, not as operational trigger support.
- [ ] Other public diagnostic triggers are treated as exploratory unless they
      improve on held-out labels under train-only selection.
- [ ] Lower-threshold OMV is treated as a follow-up candidate, not a validated
      replacement trigger.
- [ ] The three OMV-only shot `30276` detections are reviewed for physical
      pre-event timing rather than counted as broad cross-shot improvement.
- [ ] The extra OMV6 false trigger in shot `30421` is considered when deciding
      whether the recall gain is worth the noise cost.
- [ ] The fresh-split OMV6 result is treated as negative for fixed-threshold
      OMV replacement because recall is unchanged and false triggers increase.
- [ ] Later unused-shot trigger searches are treated as recall/noise tradeoffs,
      not clean operational trigger improvements.

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
- [ ] Forward-surrogate penalties and policy rankings are treated as proxy
      assumptions, not sustained-fusion performance.
- [ ] Sensitivity grid is broad enough, or stricter falsification assumptions
      are requested.
- [ ] Reviewer agrees with stated claim boundaries.

## Requested Outcome

- [ ] Accept packet as credible preliminary experimental precursor evidence.
- [ ] Request changes to labeling rules.
- [ ] Request additional diagnostics.
- [ ] Reject precursor interpretation.

Reviewer notes:

```text

```
