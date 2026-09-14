# TCT Git Research Pipeline

This directory turns the research branch into a small asynchronous job queue between ChatGPT/GitHub and the Ubuntu M3D-C1 machine.

## Flow

1. The research side publishes code plus one JSON job into `agent_pipeline/jobs/`.
2. The Ubuntu worker polls `agent/tct-pulse-train-audit`, fast-forwards, and selects the first enabled job without a matching result receipt.
3. The worker executes exactly one allow-listed runner matching `tools/tct_mechanism_explorer/run_*.sh`.
4. The worker captures stdout/stderr to `agent_pipeline/logs/<job_id>.log`.
5. The declared validation output, the log, and `agent_pipeline/results/<job_id>.json` are committed and pushed back to the same branch.
6. The research side reads the new result, preserves the formal classification/claim boundary, and may publish at most one scientifically justified follow-up job.

The machine worker intentionally runs one job per invocation so sequential experiments can depend on the interpretation of the previous result.

## Job schema

Example:

```json
{
  "schema_version": 1,
  "job_id": "20260914-001-two-profile-handoff",
  "enabled": true,
  "runner": "tools/tct_mechanism_explorer/run_native_two_profile_handoff_audit.sh",
  "timeout_seconds": 7200,
  "result_paths": [
    "validation_runs/m3dc1_tct_native_two_profile_handoff"
  ],
  "summary_path": "validation_runs/m3dc1_tct_native_two_profile_handoff/native_two_profile_handoff_summary.json",
  "purpose": "Test whether uninterrupted spatial-profile handoff removes the t=0.14-0.16 failure mode."
}
```

Security/operational constraints:

- `job_id` is restricted to letters, numbers, dot, underscore, and dash.
- runners must live under `tools/tct_mechanism_explorer/` and match `run_*.sh`.
- result paths must remain inside the repository.
- timeout is limited to 60 seconds through 24 hours.
- the worker refuses to pull when tracked or staged human edits are present.
- an advisory lock prevents overlapping worker invocations.
- only declared result paths plus the pipeline receipt/log are staged for the result commit.
- result pushes rebase on newer research commits, allowing a new job to be published while a previous job is running.

## Install on Ubuntu

From the research checkout:

```bash
cd /home/ubuntu/work/openmc/sweep
git pull --ff-only origin agent/tct-pulse-train-audit
bash tools/agent_pipeline/install_tct_git_worker.sh
```

The installer creates a user-level systemd oneshot service and a timer that polls every two minutes by default. No sudo is required for installation.

To run a poll immediately:

```bash
systemctl --user start tct-git-worker.service
```

To watch it:

```bash
journalctl --user -u tct-git-worker.service -f
```

To inspect the schedule:

```bash
systemctl --user list-timers tct-git-worker.timer
```

To change the polling interval before installation, for example to five minutes:

```bash
TCT_PIPELINE_INTERVAL=5min bash tools/agent_pipeline/install_tct_git_worker.sh
```

If the machine must continue running the user timer while the account is logged out, optionally enable lingering once:

```bash
sudo loginctl enable-linger "$USER"
```

## Result semantics

A result receipt records the job id, runner hash, Git head before execution, timestamps, return code, timeout/error state, log hash, summary hash/path, host/runtime metadata, and the parsed summary when available. The actual validation outputs are committed under their declared `validation_runs/...` path.

A failed scientific classification is still a successful pipeline execution when the runner returns zero. A nonzero runner exit, timeout, malformed job, Git failure, or summary parse problem is recorded as a pipeline error rather than being interpreted as physics.
