# FAIR-MAST TCT Validation Summary

## Bottom Line

The FAIR-MAST pipeline supports a reduced-order experimental prerequisite for
TCT-style preventative control:

- public MAST signals contain held-out Mirnov/SXR precursor information for many
  accepted D-alpha events,
- timing supports standing bias plus fast bounded boost for a useful subset of
  events,
- reduced-order forward surrogate and sensitivity sweeps favor clean fast
  Mirnov-class triggering over noisy high-recall SXR triggering.

This does **not** validate sustained fusion, causal TCT suppression, a measured
TCT actuator, burn physics, alpha heating, wall survival, TBR, or reactor
duty-cycle behavior.

## Strongest Results

| Result | Current Evidence |
| --- | --- |
| Conservative event set | `59` accepted `true_elm` events after machine-aided label triage |
| Fixed Mirnov precursor | `39/59` accepted events detected, median lead `8.376 ms` |
| Mirnov+toroidal fusion | `40/59` accepted events detected, `8` false triggers |
| Raw SXR recognition ceiling | up to `58/59` detected, but `54` false triggers and shorter lead |
| SXR morphology gate | completed; selected gate detects `57/59` but with `89` false triggers, so not operationally better |
| Other-trigger screen | OMV/BES/density/bolometer/controller/gas/coil/radiation screen completed; train-selected OMV augmentation was held-out neutral (`39/59`, `8` false triggers), while exploratory held-out ranking found only a marginal OMV lead (`42/59`, `9` false triggers) |
| OMV follow-up | OMV `6 sigma` adds `3` detections and `1` false trigger, loses no baseline detections, and is positive in `4/5` leave-one-shot-out folds; the recall gain is localized to shot `30276`, so this remains exploratory |
| OMV fresh split | fixed OMV `6 sigma` candidate tested on unused shots `30260`, `30261`, `30262`, `30263`, `30265`; no recall gain vs baseline (`50/61` both) and `+6` false triggers, so the fresh split does not support OMV6 as a replacement trigger |
| Fresh trigger searches | broad unused-shot searches found no clean replacement trigger; `Mirnov8+OMV4` gained recall but added many false triggers, while later `pol_cc_all=5` gave only a marginal recall/noise tradeoff (`43/59` vs `35/59`, `+7` false triggers) |
| Strict nulls | block-shift and event-jitter nulls remain significant |
| Fast response budget | prebiased fast current-sheet budget reaches `38/59` accepted events |
| Forward surrogate | Mirnov+toroidal fast boost gives `51.5%` proxy loss reduction vs no control |
| Sensitivity sweep | Mirnov+toroidal tied for best realizable policy in `320/320` swept scenarios |

## What Would Falsify Or Downgrade This

- Expert review rejects many accepted D-alpha `true_elm` labels.
- Representative Mirnov triggers are judged to be event signatures rather than
  physically useful pre-event precursors.
- A stricter null model removes the timing-specific association.
- A measured actuator response is slower than the fast/nominal biased-current
  budgets used here.
- Reviewer-selected false-trigger penalties, weaker boost efficacy, or
  standing-bias costs fall outside the sensitivity grid and reverse the policy
  ranking.
- A stronger SXR morphology/classifier gate cannot reduce false triggers without
  losing the recognition advantage.

## Open Gaps

- No expert-reviewed ELM label set.
- No measured TCT actuator transfer function.
- No causal suppression experiment.
- No SXR morphology/classifier trigger clean enough to replace Mirnov/toroidal
  fusion.
- No train-selected or fresh-split non-SXR public diagnostic trigger that
  improves the Mirnov baseline.
- Lower-threshold OMV did not generalize in the fresh split; it matched
  baseline recall while increasing false triggers.
- Later unused-shot searches found recall/noise tradeoffs, but no clean
  trigger that improves recall while preserving false-trigger behavior.
- No DIII-D/NSTX/ITER EFIT/MHD experimental validation of TCT.
- No reactor burn, transport, neutronics, material-survival, or TBR validation
  from the FAIR-MAST pipeline.

## Reviewer Path

Start with:

- [External review packet](validation_runs/fair_mast_external_review_packet_default/EXTERNAL_REVIEW_PACKET.md)
- [Review checklist](validation_runs/fair_mast_external_review_packet_default/REVIEW_CHECKLIST.md)
- [Claim gate summary](validation_runs/fair_mast_claim_gate_default/fair_mast_claim_gate_report.md)

Primary recent reports:

- [SXR precursor tradeoff](validation_runs/fair_mast_sxr_precursor_tradeoff_default/fair_mast_sxr_precursor_tradeoff_report.md)
- [Forward surrogate](validation_runs/fair_mast_tct_forward_surrogate_default/fair_mast_tct_forward_surrogate_report.md)
- [Forward sensitivity sweep](validation_runs/fair_mast_tct_forward_sensitivity_default/fair_mast_tct_forward_sensitivity_report.md)
- [SXR morphology gate](validation_runs/fair_mast_sxr_morphology_gate_default/fair_mast_sxr_morphology_gate_report.md)
- [Other trigger screen](validation_runs/fair_mast_other_trigger_screen_default/fair_mast_other_trigger_screen_report.md)
- [OMV follow-up](validation_runs/fair_mast_omv_followup_default/fair_mast_omv_followup_report.md)
- [OMV fresh split](validation_runs/fair_mast_omv_fresh_split_default/fair_mast_omv_fresh_split_report.md)
- [Fresh trigger search](validation_runs/fair_mast_fresh_trigger_search_default/fair_mast_fresh_trigger_search_report.md)
- [Mirnov8+OMV4 validation](validation_runs/fair_mast_mirnov8_omv4_validation_default/fair_mast_mirnov8_omv4_validation_report.md)
- [Rolling fresh trigger search](validation_runs/fair_mast_fresh_trigger_search_skip20_small_default/fair_mast_fresh_trigger_search_report.md)

## Public Wording

Defensible:

> Public FAIR-MAST diagnostics provide preliminary held-out support for the
> timing prerequisite of a standing-bias plus fast bounded-boost TCT control
> strategy in a reduced-order proxy.

Not defensible:

> TCT is experimentally validated, causally suppresses ELMs, or sustains fusion.
