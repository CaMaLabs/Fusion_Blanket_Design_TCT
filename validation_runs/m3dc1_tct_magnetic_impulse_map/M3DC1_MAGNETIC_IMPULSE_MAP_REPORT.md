# M3D-C1 Magnetic Impulse Map Report

Primary classification: `M3DC1_MAGNETIC_RESPONSE_SIGN_REVERSAL`

## Frozen Matrix

- amp: `-0.01`
- duration: `0.05`
- ramp: `0.0`
- dt: `0.01`
- ntimemax: `40`
- pulse starts: `[0.0, 0.05, 0.1, 0.15, 0.2]`

## Case Results

- `impulse_t000` t_on=0.0: BROADENING_RESPONSE; peak dW=0.019830366, dJpk=0.001108, full_authority=False, latency=0.06, zero_cross=0.07
- `impulse_t005` t_on=0.05: BROADENING_RESPONSE; peak dW=0.029549877, dJpk=0.000663, full_authority=False, latency=0.07, zero_cross=0.13
- `impulse_t010` t_on=0.1: BROADENING_RESPONSE; peak dW=0.01998083, dJpk=0.001822, full_authority=False, latency=0.06, zero_cross=0.17
- `impulse_t015` t_on=0.15: BROADENING_RESPONSE; peak dW=0.018779364, dJpk=0.001949, full_authority=False, latency=0.06, zero_cross=0.22
- `impulse_t020` t_on=0.2: BROADENING_RESPONSE; peak dW=0.01386975, dJpk=0.00014, full_authority=False, latency=0.06, zero_cross=0.27

## Interpretation

All tested timings are field-reachable and produce a positive peak sheet-width response, but none has full impulse authority at the peak-width sample because peak `Jpk` is not reduced there. Each response also crosses back through zero shortly after the peak, explaining why continuous fixed drive failed.

## Claim Boundary

This is a native normalized magnetic impulse response map. It is not a TCT validation pass and not a lithium dimensional-transfer result.
