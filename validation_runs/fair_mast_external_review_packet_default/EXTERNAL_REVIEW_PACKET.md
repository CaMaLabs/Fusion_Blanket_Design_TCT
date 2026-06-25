# FAIR-MAST External Review Packet

## Request

Please review whether the FAIR-MAST held-out precursor analysis supports a
credible experimental prerequisite for TCT-style preventative control:

1. the automatic D-alpha event labels are plausible ELM labels,
2. the Mirnov-envelope triggers are genuinely pre-event rather than event
   signatures,
3. the measured lead times are large enough to justify bounded actuator
   adjustment in a future controller, and
4. the remaining caveats are correctly stated.

This packet is not asking the reviewer to endorse causal TCT validation.

## Public Data And Reproduction

- Data source: public FAIR-MAST Level-1 and Level-2 archives.
- Held-out shots: `30276`, `30277`, `30418`, `30419`, `30421`.
- Event marker: fixed-channel D-alpha peak detection.
- Candidate precursor: fixed-channel centre-column Mirnov high-pass/RMS envelope.
- Train/test split: threshold multiplier selected on training shots `30311` and
  `30423`, evaluated on held-out shots only.

Primary reproduction scripts:

- [`fair_mast_prospective_precursor_test.py`](../../fair_mast_prospective_precursor_test.py)
- [`fair_mast_event_label_audit.py`](../../fair_mast_event_label_audit.py)
- [`fair_mast_machine_reviewed_label_metrics.py`](../../fair_mast_machine_reviewed_label_metrics.py)
- [`fair_mast_precursor_time_shift_null.py`](../../fair_mast_precursor_time_shift_null.py)
- [`fair_mast_precursor_strict_null_suite.py`](../../fair_mast_precursor_strict_null_suite.py)
- [`fair_mast_actuator_latency_feasibility.py`](../../fair_mast_actuator_latency_feasibility.py)
- [`fair_mast_biased_actuator_response_budget.py`](../../fair_mast_biased_actuator_response_budget.py)
- [`fair_mast_multidiagnostic_precursor_fusion.py`](../../fair_mast_multidiagnostic_precursor_fusion.py)
- [`fair_mast_sxr_precursor_tradeoff.py`](../../fair_mast_sxr_precursor_tradeoff.py)
- [`fair_mast_sxr_morphology_gate.py`](../../fair_mast_sxr_morphology_gate.py)
- [`fair_mast_other_trigger_screen.py`](../../fair_mast_other_trigger_screen.py)
- [`fair_mast_tct_forward_surrogate.py`](../../fair_mast_tct_forward_surrogate.py)
- [`fair_mast_tct_forward_sensitivity.py`](../../fair_mast_tct_forward_sensitivity.py)

## Result Summary

Held-out automatic-label precursor screen:

- Test events: `73`
- Detected events: `47`
- Missed events: `26`
- False triggers: `1`
- Precision: `0.979`
- Recall: `0.644`
- Median detected-event lead: `8.233 ms`

Machine-aided conservative label triage:

- Input events: `73`
- Accepted `true_elm`: `59`
- Ambiguous: `14`
- Accepted detected: `39`
- Accepted missed: `20`
- Precision on accepted true ELMs: `0.975`
- Recall on accepted true ELMs: `0.661`
- Median detected lead: `8.376 ms`

Time-shift null test on accepted true ELMs:

- Monte Carlo trials: `50000`
- Null model: circularly shift observed trigger times independently within each
  shot window while preserving trigger count per shot.
- Observed detected true ELMs: `39`
- Null mean detected count: `27.700`
- Null 95th percentile detected count: `33.000`
- Null max detected count: `38`
- Directional p for null detected count >= observed: `0.000020`

Stricter null suite:

- Trigger-train block shift preserves each shot's trigger burst pattern and
  inter-trigger spacing.
- Local event-jitter keeps trigger times fixed and resamples each accepted event
  inside its midpoint-bounded local interval.
- Full held-out set, trigger-train block shift: observed `39`, null mean
  `27.725`, null p95 `33`, directional p `0.000060`.
- Full held-out set, local event-jitter: observed `39`, null mean `32.137`,
  null p95 `35`, directional p `0.000300`.
- Leave-one-shot-out sensitivity remains significant for every held-out shot
  removed under both null families.

Actuator-latency feasibility:

- Detected accepted true-ELM lead distribution: minimum `2.554 ms`, median
  `8.376 ms`, maximum `14.958 ms`.
- End-to-end latency <= `3 ms` supports a precursor-gated bounded boost layered
  on preventative bias.
- Around `5 ms`, precursor-gated boost is still plausible with no settle margin,
  but becomes constrained once a `1-2 ms` settle margin is required.
- At `8-12 ms`, event-specific response is too limited; the defensible policy is
  slow preventative scheduling with at most limited boost on a subset of events.

Biased actuator response budget:

- Fast prebiased current-sheet modulation budget: `2.750 ms`, reaches `38/59`
  accepted true ELMs, verdict `passes_for_bounded_boost`.
- Nominal prebiased current-sheet modulation budget: `5.250 ms`, reaches
  `30/59` accepted true ELMs, verdict `passes_for_bounded_boost`.
- Slow prebiased chain (`8.250 ms`) and cold-start current pulse (`9.000 ms`)
  fail reliable event-specific boost.
- Mechanical/thermal liquid-lithium response (`25.750 ms`) is not
  event-specific; it can only be part of the standing bias interpretation.

Multi-diagnostic precursor fusion:

- Candidate signals: fixed-channel centre-column poloidal Mirnov RMS,
  multi-channel centre-column poloidal/toroidal Mirnov RMS, public soft-X-ray
  camera envelopes, and D-alpha positive slope.
- Train-selected SXR-assisted trigger: fixed poloidal Mirnov channel plus
  tangential SXR aggregate RMS at `4.0` sigma.
- Accepted true ELMs detected: `57/59`, compared with `39/59` for the fixed
  single-channel baseline.
- False triggers: `89`, compared with `8` baseline.
- Median lead: `3.810 ms`, compared with `8.376 ms` baseline.
- Latency-reachable event counts fall from `38/30/23/9` to `34/20/11/5` at
  `3/5/8/12 ms`.
- Interpretation: public SXR contains substantial precursor/event-recognition
  information, but this threshold-fusion trigger is not operationally cleaner.

SXR precursor tradeoff:

- Best raw SXR recognition: upper horizontal SXR aggregate RMS at `4.0` sigma,
  `58/59` detected, `54` false triggers, precision `0.518`, median lead
  `3.877 ms`.
- Best false-bounded SXR: lower horizontal SXR aggregate RMS at `4.0` sigma,
  `40/59` detected, `8` false triggers, precision `0.833`, median lead
  `8.096 ms`.
- Best false-bounded tested trigger remains Mirnov+toroidal RMS: `40/59`,
  `8` false triggers, precision `0.833`, median lead `8.360 ms`.
- Best SXR result with precision >= `0.75`: tangential SXR at `8.0` sigma,
  `42/59` detected, `13` false triggers, precision `0.764`, median lead
  `7.182 ms`.
- Interpretation: the next improvement path is not another fixed threshold; it
  is a classifier or morphology gate that separates useful SXR precursors from
  SXR-only event signatures and shot-specific bursts.

SXR morphology gate:

- Gate design: retain the fixed Mirnov trigger, then admit SXR candidates only
  when low-threshold poloidal/toroidal Mirnov state is already elevated or has
  crossed recently.
- Train/test protocol: select the gate only on training shots `30311` and
  `30423`, then evaluate once on held-out reviewed labels.
- Selected gate: tangential SXR aggregate RMS at `4.0` sigma with no magnetic
  gate requirement.
- Held-out result: `57/59` accepted events detected, `89` false triggers,
  precision `0.390`, median lead `3.810 ms`.
- Interpretation: this simple causal gate did not beat Mirnov+toroidal fusion;
  a stronger classifier or additional diagnostic features are needed before SXR
  can be treated as an operational trigger.

Other public diagnostic trigger screen:

- Candidate families: OMV/OMAHA/saddle magnetics, sparse BES,
  density-gradient, alternate D-alpha channels, bolometer, controller/gas,
  coil/passive-current, and summary radiation traces.
- Train/test protocol: select candidate thresholds on training shots `30311`
  and `30423`, then evaluate once on held-out reviewed labels.
- Train-selected result: fixed Mirnov plus OMV at `10.0` sigma is held-out
  neutral against the fixed Mirnov baseline, with `39/59` detected and `8`
  false triggers.
- Exploratory held-out oracle ranking: fixed Mirnov plus OMV at `6.0` sigma
  reaches `42/59` detected with `9` false triggers, precision `0.824`, and
  median lead `8.413 ms`.
- Interpretation: no clean train-selected non-SXR trigger improvement was
  found. The lower-threshold OMV result is a lead for a future pre-registered
  split, not a validation-selected replacement trigger.

FAIR-MAST-seeded forward TCT surrogate:

- Monte Carlo policies: no control, preventative bias only, fixed Mirnov fast
  boost, Mirnov+toroidal fast boost, Mirnov+toroidal nominal boost, high-recall
  SXR, precision-gated SXR, false-bounded SXR, and oracle fast upper bound.
- Calibration: `59` accepted FAIR-MAST true ELMs over `0.90 s` held-out
  windows, D-alpha contrast severity proxy, held-out trigger/latency metrics,
  and biased actuator response budgets.
- Best realizable policy in the proxy: Mirnov+toroidal fast boost, mean proxy
  loss `358.578`, `51.5%` lower than no control.
- Preventative bias only: mean proxy loss `556.006`, `24.8%` lower than no
  control.
- Noisy high-recall SXR: mean proxy loss `393.099`, `46.8%` lower than no
  control, worse than Mirnov+toroidal because shorter leads and false triggers
  reduce control usefulness.
- Oracle fast upper bound: mean proxy loss `250.005`, `66.2%` lower than no
  control.
- Interpretation: this supports the control strategy ranking in a reduced-order
  proxy, not sustained-fusion validation.

Forward-surrogate sensitivity / falsification sweep:

- Scenarios: `320` deterministic expected-loss cases.
- Swept assumptions: standing-bias reduction `0.10-0.35`, boost reduction
  `0.25-0.70`, false-trigger penalty `0-5x`, and event-rate multiplier
  `0.25-2x`.
- Result: Mirnov+toroidal fast boost is tied for best realizable policy in
  `320/320` scenarios and within `1%` of best in `320/320` scenarios.
- Deterministic tie-break note: fixed Mirnov baseline is listed as winner in
  the win-rate table because it has the same `3 ms` reachability and false
  trigger count as Mirnov+toroidal in the input table.
- Mean Mirnov+toroidal loss reduction vs no control across the sweep: `46.0%`.
- Range of Mirnov/toroidal loss reduction vs no control: `23.0%` to `64.3%`.
- Falsifier rows found: `0` within the swept parameter grid.

## Audit Artifacts

- [Held-out precursor report](../fair_mast_prospective_precursor_default/fair_mast_prospective_precursor_report.md)
- [Event-label audit report](../fair_mast_event_label_audit_default/fair_mast_event_label_audit_report.md)
- [Event-label audit manifest](../fair_mast_event_label_audit_default/fair_mast_event_label_audit_manifest.csv)
- [Machine-reviewed label report](../fair_mast_machine_reviewed_labels_default/fair_mast_machine_reviewed_label_report.md)
- [Machine-reviewed label manifest](../fair_mast_machine_reviewed_labels_default/fair_mast_machine_reviewed_label_manifest.csv)
- [Time-shift null report](../fair_mast_precursor_time_shift_null_default/fair_mast_precursor_time_shift_null_report.md)
- [Strict null suite report](../fair_mast_precursor_strict_null_suite_default/fair_mast_precursor_strict_null_suite_report.md)
- [Actuator-latency feasibility report](../fair_mast_actuator_latency_feasibility_default/fair_mast_actuator_latency_feasibility_report.md)
- [Biased actuator response-budget report](../fair_mast_biased_actuator_response_budget_default/fair_mast_biased_actuator_response_budget_report.md)
- [Multi-diagnostic precursor fusion report](../fair_mast_multidiagnostic_precursor_fusion_default/fair_mast_multidiagnostic_precursor_fusion_report.md)
- [SXR precursor tradeoff report](../fair_mast_sxr_precursor_tradeoff_default/fair_mast_sxr_precursor_tradeoff_report.md)
- [SXR morphology gate report](../fair_mast_sxr_morphology_gate_default/fair_mast_sxr_morphology_gate_report.md)
- [Other trigger screen report](../fair_mast_other_trigger_screen_default/fair_mast_other_trigger_screen_report.md)
- [TCT forward surrogate report](../fair_mast_tct_forward_surrogate_default/fair_mast_tct_forward_surrogate_report.md)
- [TCT forward sensitivity report](../fair_mast_tct_forward_sensitivity_default/fair_mast_tct_forward_sensitivity_report.md)

Representative plots:

- [Clear triggered event: shot 30277 event 009](../fair_mast_event_label_audit_default/plots/shot_30277_event_009_triggered.png)
- [Clear missed event: shot 30276 event 008](../fair_mast_event_label_audit_default/plots/shot_30276_event_008_missed.png)
- [Duplicate-trigger review case: shot 30418 event 014](../fair_mast_event_label_audit_default/plots/shot_30418_event_014_triggered.png)
- [Short-lead review case: shot 30421 event 005](../fair_mast_event_label_audit_default/plots/shot_30421_event_005_triggered.png)

## Specific Questions For Reviewer

1. Are the accepted `true_elm` D-alpha events credible enough for this level of
   precursor validation?
2. Should any of the `ambiguous` rows be promoted to `true_elm` or rejected as
   artifacts?
3. Are the duplicate-trigger rows correctly treated as ambiguous rather than
   counted as independent successful detections?
4. Does the Mirnov RMS-envelope trigger appear physically pre-event in the
   representative plots, or is it likely part of the ELM onset/signature?
5. Is the `0.5-15 ms` precursor association window defensible for this
   diagnostic pair?
6. Is the time-shift null model a fair chance-alignment control, or should a
   stricter null be used?
7. Do the stricter block-shift, event-jitter, and leave-one-shot-out nulls
   adequately address trigger clustering and shot-dominance concerns?
8. Does the latency-feasibility sweep draw the correct boundary between
   precursor-gated boost and slow preventative scheduling?
9. Is the standing lithium/current bias interpretation physically plausible,
   and are the response-budget components reasonable?
10. Is `5-8 ms` lead enough to justify bounded actuator adjustment in a future
    controller, assuming actuator response is independently characterized?
11. Does the multi-diagnostic fusion result justify replacing the fixed
    single-channel trigger, or is the one-event gain too small?
12. Is the SXR recognition gain physically pre-event, or mostly SXR event
    signature leakage that requires a morphology gate?
13. Does the forward surrogate use reasonable proxy penalties for event
    severity, false triggers, and standing-bias cost?
14. Is the sensitivity grid broad enough to stress the forward-surrogate
    ranking, or should reviewers add harsher false-trigger or weaker-boost
    assumptions?
15. Does the exploratory lower-threshold OMV result justify a fresh
    pre-registered validation split, or is it likely another shot/window
    artifact?
16. What additional FAIR-MAST diagnostics should be included before promoting
    the claim?

## Current Claim Boundary

Supported:

- Public experimental MAST signals contain a held-out, temporally specific
  Mirnov-envelope precursor association for many accepted D-alpha events.
- The association survives conservative machine-aided label triage.
- The alignment beats a per-shot circular time-shift null.
- Adding toroidal Mirnov RMS or false-bounded SXR yields a small held-out
  recall improvement (`40/59` vs `39/59`) without increasing false triggers.
- SXR envelopes can raise raw held-out recognition as high as `58/59`, but only
  with many false triggers and shorter median lead under fixed thresholds.
- The simple causal SXR morphology gate completed but did not produce a clean
  operational trigger.
- The broad non-SXR trigger screen found no train-selected held-out
  improvement over the fixed Mirnov baseline; lower-threshold OMV is only an
  exploratory follow-up candidate.
- A reduced-order forward surrogate ranks standing bias plus fast Mirnov/toroidal
  boost above no control, preventative bias only, nominal-latency boost, and
  noisy high-recall SXR under the current proxy assumptions.
- Sensitivity sweep finds no falsifier rows for Mirnov/toroidal fast boost
  within the current reduced-order proxy grid.

Not supported:

- Causal TCT actuator mitigation.
- Final expert-reviewed ELM labeling.
- Machine-specific DIII-D, NSTX, ITER, or M3D-C1 validation.
- Real-time controller deployment readiness.
- Proof that actuator latency is low enough.
- Measured TCT actuator transfer function or suppression response.
- Mechanical or thermal liquid-lithium motion as an event-specific actuator.
- A substantially better precursor that resolves the latency limitation.
- A fixed-threshold SXR trigger clean enough to replace Mirnov+toroidal fusion.
- A fixed-threshold or simple morphology-gated SXR trigger clean enough to
  replace Mirnov+toroidal fusion.
- A train-selected public non-SXR trigger that substantially improves the
  held-out Mirnov baseline.
- Sustained-fusion validation, burn control, alpha heating, transport, wall
  survival, TBR, or reactor duty-cycle prediction from the forward surrogate.
- Robustness outside the stated sensitivity grid.
