# FAIR-MAST Biased TCT Actuator Response Budget

- Status: `MAST_BIASED_ACTUATOR_RESPONSE_BUDGET_COMPLETED`
- Purpose: test whether a standing liquid-lithium/current bias could leave enough low-ms response budget for precursor-gated bounded adjustment
- Input: FAIR-MAST accepted `true_elm` detected lead distribution
- Scope: timing budget only; not a measured actuator transfer function
- Accepted true ELMs: `59`
- Detected accepted true ELMs: `39`
- Lead median: `8.376 ms`

## Scenario Results

| Scenario | Total response | Reachable accepted events | Reachable detected events | Verdict |
| --- | ---: | ---: | ---: | --- |
| `prebiased_current_sheet_fast` | 2.750 ms | 38/59 (0.644) | 0.974 | `passes_for_bounded_boost` |
| `prebiased_current_sheet_nominal` | 5.250 ms | 30/59 (0.508) | 0.769 | `passes_for_bounded_boost` |
| `prebiased_current_sheet_slow` | 8.250 ms | 21/59 (0.356) | 0.538 | `fails_event_specific_boost` |
| `cold_start_current_pulse` | 9.000 ms | 16/59 (0.271) | 0.410 | `fails_event_specific_boost` |
| `flow_or_thermal_lithium_response` | 25.750 ms | 0/59 (0.000) | 0.000 | `not_event_specific` |

## Interpretation

A standing lithium/current bias is the only framing that remains compatible
with the measured FAIR-MAST lead times. The fast and nominal prebiased
current-sheet scenarios fit enough measured precursor leads for bounded
boost. A slower biased chain is only a subset capability. Cold-start current
pulsing and mechanical/thermal lithium response are not supported as
event-specific mechanisms.

This supports the design interpretation that TCT should be framed as
moderate preventative bias plus bounded precursor-gated adjustment, not a
late strong pulse created from zero after event onset.

## Claim Boundary

This does not prove liquid-lithium/current coupling, magnetic topology,
plasma suppression, or actuator hardware performance. It only shows which
response-budget classes are compatible with validated precursor lead times.
