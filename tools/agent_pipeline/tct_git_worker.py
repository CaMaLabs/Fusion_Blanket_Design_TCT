#!/usr/bin/env python3
"""Git-backed TCT research worker.

The worker treats Git as a small research job queue:
  1. pull the configured branch,
  2. find the first enabled job without a result receipt,
  3. run one allow-listed TCT shell runner,
  4. write a machine-readable result receipt and full log,
  5. commit declared validation outputs + receipt/log,
  6. rebase/push the result commit back to the same branch.

It intentionally executes at most one job per invocation. A systemd timer can
invoke it frequently without overlapping because the worker also takes a lock.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("TCT_PIPELINE_REPO", "/home/ubuntu/work/openmc/sweep")).resolve()
BRANCH = os.environ.get("TCT_PIPELINE_BRANCH", "agent/tct-pulse-train-audit")
REMOTE = os.environ.get("TCT_PIPELINE_REMOTE", "origin")
PIPELINE = REPO / "agent_pipeline"
JOBS = PIPELINE / "jobs"
RESULTS = PIPELINE / "results"
LOGS = PIPELINE / "logs"
LOCK = REPO / ".git" / "tct-agent-pipeline.lock"

JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
RUNNER_RE = re.compile(r"^tools/tct_mechanism_explorer/run_[A-Za-z0-9_.-]+\.sh$")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], *, check: bool = True, capture: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        timeout=timeout,
    )
    if check and p.returncode != 0:
        out = p.stdout or ""
        raise RuntimeError(f"command failed rc={p.returncode}: {' '.join(cmd)}\n{out[-6000:]}")
    return p


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def ensure_repo_ready() -> None:
    if not (REPO / ".git").exists():
        raise RuntimeError(f"not a git checkout: {REPO}")
    current = git("branch", "--show-current").stdout.strip()
    if current != BRANCH:
        raise RuntimeError(f"worker requires branch {BRANCH!r}, current branch is {current!r}")
    # Refuse to overwrite human edits to tracked files. Untracked files are left alone.
    if git("diff", "--quiet", check=False).returncode != 0:
        raise RuntimeError("tracked working-tree edits exist; refusing automatic pull/run")
    if git("diff", "--cached", "--quiet", check=False).returncode != 0:
        raise RuntimeError("staged edits exist; refusing automatic pull/run")


def pull_latest() -> None:
    git("fetch", REMOTE, BRANCH)
    git("merge", "--ff-only", f"{REMOTE}/{BRANCH}")


def load_jobs() -> list[tuple[Path, dict]]:
    JOBS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[Path, dict]] = []
    for path in sorted(JOBS.glob("*.json")):
        try:
            job = json.loads(path.read_text())
        except Exception as exc:
            print(f"[tct-worker] skipping malformed {path.name}: {exc}", flush=True)
            continue
        job_id = str(job.get("job_id", ""))
        if not JOB_ID_RE.fullmatch(job_id):
            print(f"[tct-worker] skipping invalid job_id in {path.name}", flush=True)
            continue
        if not bool(job.get("enabled", True)):
            continue
        if (RESULTS / f"{job_id}.json").exists():
            continue
        pending.append((path, job))
    return pending


def validate_job(job_path: Path, job: dict) -> tuple[str, Path, int, list[Path], Path | None]:
    job_id = str(job["job_id"])
    runner_text = str(job.get("runner", ""))
    if not RUNNER_RE.fullmatch(runner_text):
        raise RuntimeError(
            f"job {job_id}: runner must match tools/tct_mechanism_explorer/run_*.sh"
        )
    runner = (REPO / runner_text).resolve()
    if REPO not in runner.parents or not runner.exists():
        raise RuntimeError(f"job {job_id}: runner missing/outside repo: {runner}")

    timeout = int(job.get("timeout_seconds", 7200))
    if timeout < 60 or timeout > 86400:
        raise RuntimeError(f"job {job_id}: timeout_seconds outside 60..86400")

    result_paths: list[Path] = []
    for rel in job.get("result_paths", []):
        rel_text = str(rel)
        candidate = (REPO / rel_text).resolve()
        if REPO not in candidate.parents:
            raise RuntimeError(f"job {job_id}: result path outside repo: {rel_text}")
        result_paths.append(candidate)

    summary = None
    if job.get("summary_path"):
        summary = (REPO / str(job["summary_path"])).resolve()
        if REPO not in summary.parents:
            raise RuntimeError(f"job {job_id}: summary path outside repo")

    return job_id, runner, timeout, result_paths, summary


def execute_job(job_path: Path, job: dict) -> dict:
    job_id, runner, timeout, result_paths, summary = validate_job(job_path, job)
    log_path = LOGS / f"{job_id}.log"
    receipt_path = RESULTS / f"{job_id}.json"
    started = now_utc()
    head_before = git("rev-parse", "HEAD").stdout.strip()

    print(f"[tct-worker] running {job_id}: {runner.relative_to(REPO)}", flush=True)
    rc: int | None = None
    error: str | None = None
    timed_out = False
    t0 = time.time()
    with log_path.open("w") as log:
        log.write(f"job_id={job_id}\nstarted_utc={started}\nhead_before={head_before}\n")
        log.flush()
        try:
            p = subprocess.Popen(
                ["bash", str(runner)],
                cwd=REPO,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                rc = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                error = f"timeout after {timeout} seconds"
                try:
                    os.killpg(p.pid, 15)
                    p.wait(timeout=15)
                except Exception:
                    try:
                        os.killpg(p.pid, 9)
                    except Exception:
                        pass
                rc = 124
        except Exception as exc:
            rc = 125
            error = f"launcher exception: {type(exc).__name__}: {exc}"
        log.write(f"\nfinished_utc={now_utc()}\nreturn_code={rc}\n")

    ended = now_utc()
    elapsed = time.time() - t0
    summary_data = None
    if summary and summary.exists():
        try:
            summary_data = json.loads(summary.read_text())
        except Exception as exc:
            error = (error + "; " if error else "") + f"summary parse error: {exc}"

    receipt = {
        "schema_version": 1,
        "job_id": job_id,
        "job_file": str(job_path.relative_to(REPO)),
        "runner": str(runner.relative_to(REPO)),
        "runner_sha256": sha256(runner),
        "branch": BRANCH,
        "head_before": head_before,
        "started_utc": started,
        "finished_utc": ended,
        "elapsed_seconds": elapsed,
        "return_code": rc,
        "timed_out": timed_out,
        "success": rc == 0 and error is None,
        "error": error,
        "summary_path": str(summary.relative_to(REPO)) if summary else None,
        "summary_sha256": sha256(summary) if summary else None,
        "summary": summary_data,
        "log_path": str(log_path.relative_to(REPO)),
        "log_sha256": sha256(log_path),
        "result_paths": [str(p.relative_to(REPO)) for p in result_paths],
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }
    write_json(receipt_path, receipt)

    # Stage only the queue artifacts and declared validation output. This avoids
    # accidentally committing unrelated local files.
    to_add = [job_path, receipt_path, log_path]
    to_add.extend(p for p in result_paths if p.exists())
    rels = [str(p.relative_to(REPO)) for p in to_add]
    git("add", "-A", "--", *rels)

    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print(f"[tct-worker] {job_id}: nothing to commit", flush=True)
        return receipt

    git("-c", "user.name=TCT Ubuntu Worker", "-c", "user.email=tct-worker@localhost", "commit", "-m", f"[agent-pipeline result] {job_id} rc={rc}")

    # The assistant may have published another job while this one was running.
    # Rebase the unique result commit on top of that newer head, then push.
    for attempt in range(1, 4):
        try:
            git("pull", "--rebase", REMOTE, BRANCH)
            git("push", REMOTE, f"HEAD:{BRANCH}")
            print(f"[tct-worker] pushed result for {job_id}", flush=True)
            return receipt
        except Exception as exc:
            if attempt == 3:
                raise
            print(f"[tct-worker] push retry {attempt}: {exc}", flush=True)
            time.sleep(5 * attempt)
    return receipt


def main() -> int:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lockf:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[tct-worker] another worker invocation is active", flush=True)
            return 0

        ensure_repo_ready()
        pull_latest()
        pending = load_jobs()
        if not pending:
            print("[tct-worker] no pending jobs", flush=True)
            return 0

        job_path, job = pending[0]
        try:
            receipt = execute_job(job_path, job)
        except Exception as exc:
            # Best-effort local failure receipt. If Git itself is the failing
            # component this may remain local for the user to inspect.
            job_id = str(job.get("job_id", job_path.stem))
            receipt_path = RESULTS / f"{job_id}.json"
            write_json(receipt_path, {
                "schema_version": 1,
                "job_id": job_id,
                "success": False,
                "return_code": 126,
                "error": f"worker exception: {type(exc).__name__}: {exc}",
                "finished_utc": now_utc(),
            })
            print(f"[tct-worker] ERROR {job_id}: {exc}", file=sys.stderr, flush=True)
            return 1

        return 0 if receipt.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
