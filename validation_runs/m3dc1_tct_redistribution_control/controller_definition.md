# Controller Definition

Status: not promoted to closed-loop execution.

Reason: the predeclared actuator-authority matrix did not find a native redistribution amplitude capable of opposing the measured natural sheet-narrowing rate. Running a three-state controller with this actuator would primarily test a known insufficient actuator mapping rather than the sheet-width mechanism.

Frozen state definitions retained for the next rung after actuator authority is improved:

- STATE 0, QUIET/OFF: `J_0cd = 0`
- STATE 1, EARLY/PRECONDITION: requires an amplitude with positive sustained width gain before the uncontrolled peak at `t=0.05`
- STATE 2, AGGRESSIVE ON: requires an amplitude whose induced broadening rate exceeds the natural maximum narrowing rate magnitude `1.8390386614487313`
- STATE 3, HOLD/MAINTENANCE: requires a reduced nonzero amplitude that prevents immediate re-narrowing after recovery

Trigger thresholds must be frozen from `natural_sheet_dynamics_summary.json` before any closed-loop run. The early trigger must activate before `t=0.05`; otherwise classify `TRIGGER_TOO_LATE`.
