# FAIR-MAST SXR Morphology Gate

- Status: `BLOCKED_PUBLIC_ARCHIVE_READ_FAILURE`
- Goal: train/test a causal morphology gate to keep SXR precursor recognition while rejecting SXR-only false-trigger bursts
- Script: `fair_mast_sxr_morphology_gate.py`
- Data source: public FAIR-MAST Level-2 archive at `https://s3.echo.stfc.ac.uk/mast/level2/shots`
- Attempted first shot: `30311`

## What Was Implemented

The script implements a causal gate family:

- baseline fixed-channel Mirnov trigger is retained,
- SXR candidates are generated from upper-horizontal or tangential SXR aggregate RMS envelopes,
- candidate SXR triggers are accepted only when low-threshold poloidal/toroidal Mirnov state is already elevated or has crossed recently,
- configuration selection is performed only on training shots `30311` and `30423`,
- the selected gate is then evaluated once on held-out reviewed labels for shots `30276`, `30277`, `30418`, `30419`, and `30421`.

## Run Outcome

The screen could not complete in this execution because the public FAIR-MAST object store failed during the first training-shot load.

Observed failures:

- `ShotLoadTimeout` while reading shot `30311` after a 120 s per-shot load timeout.
- `ClientConnectorDNSError` and `ClientConnectorError` while connecting to `s3.echo.stfc.ac.uk:443` on subsequent retries.
- `ClientPayloadError` / incomplete content-length payload while opening `30311.zarr` after DNS recovered.

Because the training shot could not be loaded, no morphology-gate validation metric is reported here.

## Current Interpretation

This does not change the previous SXR result: SXR envelopes contain substantial recognition information, but fixed-threshold SXR triggers are too false-trigger-heavy. The morphology-gate path remains the next reasonable open-data test once the FAIR-MAST archive is reachable again.

## Claim Boundary

This is a blocked execution artifact, not a validation pass or failure of the morphology gate.
