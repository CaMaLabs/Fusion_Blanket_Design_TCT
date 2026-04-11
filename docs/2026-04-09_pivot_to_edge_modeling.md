# Pivot Plan: From Blanket Optimization to Mainstream Edge-Event Modeling (2026-04-09)

## Why pivot now

The blanket search has produced a stable and defensible design basin. At this point, additional blanket tweaking is likely to yield only incremental gains compared with the remaining uncertainty in the plasma-side event-severity story.

Current engineering reference candidate:

- `radius_cm = 55`
- `li_current = 0.1`
- TCT supervisor aggressive
- `severity_scale = 0.6`
- topology: `be_outer_kill`
- ordering: `Be / Li2O / Li2O / W_Ti_B4C_60_30_10_wt / Be`
- split: `(0.15, 0.20, 0.40, 0.15, 0.10)`
- blanket thickness: `1.25`
- outer axial cap: `0.6`

## What has been established in the current stack

Within the present model stack, we have shown:

- a repeatable blanket winner
- improved engineering compromise by moving from `50 cm` to `55 cm`
- strong neutronics metrics with the current candidate
- evidence *within the model* that the chosen regime reduces effective event-severity burden relative to worse configurations

This is enough to freeze the blanket and move the main uncertainty to plasma-side validation.

## What has NOT been proven yet

The current workflow does **not** prove, from first principles, that the exact TCT-assisted regime suppresses real ELM severity in a reactor.

The next question is no longer:

> can we find a slightly better blanket?

It is:

> does the event-severity reduction story survive in a more mainstream edge / ELM modeling framework?

## Recommended next modeling track

### Track A: keep blanket frozen
Use the 55 cm candidate as the fixed engineering baseline.

### Track B: build a reduced edge-event testbed
Use a more mainstream edge / ELM-oriented modeling path, aimed at directional validation rather than full-fidelity tokamak signoff.

Suggested outputs:

- edge crash amplitude
- event frequency
- deposited heat pulse severity
- target heat-load proxy
- pedestal collapse severity

Suggested control variables:

- TCT-linked stabilizing influence (as a reduced control parameter)
- rotation / spin-informed modifier
- event-threshold / edge-drive parameter

## Immediate implementation plan

1. Freeze the 55 cm blanket candidate as the engineering reference.
2. Stand up a reduced edge-event runner separate from blanket optimization.
3. Parameterize one or two plasma-side control levers only.
4. Compare event amplitude / severity with and without TCT-linked stabilization.
5. Use the output to determine whether the current blanket/control regime deserves deeper physics investment.

## Decision rule

- If the reduced edge model supports the same severity-reduction direction, continue building the plasma-side case.
- If it fails, revisit the control concept before spending more time on blanket micro-optimization.

## Current strategic conclusion

The highest-value next step is to move effort from blanket refinement into a more mainstream edge-event modeling path while keeping the current 55 cm blanket candidate frozen as the reference design.
