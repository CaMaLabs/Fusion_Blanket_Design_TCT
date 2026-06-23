# FAIR-MAST Machine-Aided Event-Label Review

- Status: `MAST_MACHINE_AIDED_LABEL_REVIEW_COMPLETED`
- Scope: first-pass conservative review of the held-out FAIR-MAST event-label audit packet
- Review type: machine-aided morphology/timing triage, not expert adjudication
- Input events: `73`
- Accepted `true_elm`: `59`
- Ambiguous: `14`
- Artifact: `0`

## Reviewed Metrics

- Detected accepted true ELMs: `39`
- Missed accepted true ELMs: `20`
- Source false-trigger count carried forward: `1`
- Precision on accepted true ELMs: `0.975`
- Recall on accepted true ELMs: `0.661`
- F1 on accepted true ELMs: `0.788`
- Median detected lead: `8.376 ms`

| Required latency | Accepted true ELMs with enough detected lead |
| --- | ---: |
| `3_ms` | 38 |
| `5_ms` | 30 |
| `8_ms` | 23 |
| `12_ms` | 9 |

## Conservative Review Rules

- Duplicate trigger reuse is marked `ambiguous`.
- Analysis-window edge events are marked `ambiguous`.
- Low D-alpha peak/contrast events are marked `ambiguous`.
- Close neighboring peaks with moderate contrast are marked `ambiguous`.
- Trigger lead below 1 ms is marked `ambiguous` because precursor/event-signature separation is weak.

## Interpretation

The first-pass review preserves most of the held-out precursor result after
removing questionable labels: the accepted-event precision remains high and
median lead remains in the multi-millisecond range. This is stronger than
the unreviewed automatic-label result, but it is still not a substitute for
domain-expert event labeling or independent diagnostic confirmation.

## Claim Boundary

These labels are machine-aided triage labels. They are useful for stress
testing the automatic-label result and prioritizing expert review, but they
do not establish final experimental validation.
