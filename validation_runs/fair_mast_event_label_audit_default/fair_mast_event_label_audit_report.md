# FAIR-MAST Event-Label Audit Packet

- Status: `MAST_EVENT_LABEL_AUDIT_PACKET_GENERATED`
- Scope: held-out test events from the FAIR-MAST prospective precursor run
- Purpose: independent review of automatic D-alpha event labels and trigger timing
- Events plotted: `73`
- Shots: `[30276, 30277, 30418, 30419, 30421]`
- Plot window: `+/-20 ms` around each automatic D-alpha event

## Reviewer Instructions

Use `fair_mast_event_label_audit_manifest.csv` as the working sheet. For each
row, inspect the linked PNG and set `review_label` to one of:

- `true_elm`
- `ambiguous`
- `artifact`
- `missed_obvious_elm_nearby`

Then fill `review_notes` with the basis for that call. The manifest already
contains trigger timing, lead time, latency-feasibility flags, and simple
D-alpha local-peak context to make the review auditable.

## Current Automatic-Label Summary

- Source aggregate trigger-detected events: `47`
- Source aggregate missed automatic events: `26`
- Raw event-row trigger flags: `48` detected / `25` missed
- Event rows with reused trigger times requiring audit attention: `4`
- Events with at least 3 ms lead: `45`
- Events with at least 5 ms lead: `36`
- Events with at least 8 ms lead: `26`
- Events with at least 12 ms lead: `11`

## Claim Boundary

This packet does not itself prove the event labels. It creates the review set
needed to replace automatic labels with audited labels, after which precision,
recall, false-trigger rate, and lead-time feasibility should be recomputed on
accepted `true_elm` rows only.
