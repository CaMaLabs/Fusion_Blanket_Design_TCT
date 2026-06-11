# Limited DIII-D Diagnostic Data Access Request

We reconstructed the public EFIT equilibrium and fitted profiles for DIII-D
shot `158103` at `3796.325 ms` and prepared a directly falsifiable
precursor-timing test.

## Requested scope

- Read-only data for shot `158103`
- Time window: `3756.325` to `3806.325 ms`
- Required quantities: magnetic fluctuation/precursor signal, edge ECE,
  density, established event marker, and plasma current
- Preferred additions: applicable actuator command/response and EFIT time evolution

## Question

Does a reproducible magnetic-growth precursor occur before the event marker,
is it corroborated by an independent edge channel, and is its measured lead
time longer than the sensing plus actuator latency?

## Precommitted outcomes

- No robust precursor: diagnostic-trigger claim fails for this event.
- Precursor but insufficient lead: real-time preemptive control is unsupported
  for the tested latency.
- Robust precursor with sufficient lead: proceed to a supported actuator-model
  study; this alone does not validate TCT control.

The repository contains the reconstruction script, standardized replacement
contract, synthetic traces, and pass/fail criteria so authorized users can
replace the reconstructed columns with raw data without redesigning the test.
