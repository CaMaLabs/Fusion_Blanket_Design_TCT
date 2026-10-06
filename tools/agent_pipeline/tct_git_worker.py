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
RUNTIME_WRAPPER = REPO / "tools" / "agent_pipeline" / "run_tct_job.sh"

JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
RUNNER_RE = re.compile(r"^tools/tct_mechanism_explorer/run_[A-Za-z0-9_.-]+\.sh$")
MAX_ARTIFACT_FILE_BYTES = int(os.environ.get("TCT_PIPELINE_MAX_ARTIFACT_FILE_BYTES", str(95 * 1024 * 1024)))
MAX_ARTIFACT_TOTAL_BYTES = int(os.environ.get("TCT_PIPELINE_MAX_ARTIFACT_TOTAL_BYTES", str(256 * 1024 * 1024)))

# Fail immediately if runner validation is accidentally broken by escaping or
# refactoring. These are representative allow/deny cases for the queue contract.
_RUNNER_VALIDATION_PROBES = {
    "tools/tct_mechanism_explorer/run_probe.sh": True,
    "tools/tct_mechanism_explorer/run_probe.py": False,
    "tools/tct_mechanism_explorer/audit_probe.sh": False,
    "../tools/tct_mechanism_explorer/run_probe.sh": False,
}
for _runner_probe, _expected in _RUNNER_VALIDATION_PROBES.items():
    _actual = RUNNER_RE.fullmatch(_runner_probe) is not None
    if _actual != _expected:
        raise RuntimeError(
            f"internal runner validator self-check failed for {_runner_probe!r}: "
            f"expected {_expected}, got {_actual}"
        )


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
    # This branch has two legitimate writers: the research side publishes jobs
    # and the Ubuntu worker publishes results. If both advance before the next
    # poll, the local branch can diverge even with a clean working tree. Rebase
    # local-only worker commits onto the remote head rather than deadlocking on
    # an ff-only merge. ensure_repo_ready() has already rejected tracked/staged
    # working-tree edits before we reach this point.
    git("rebase", f"{REMOTE}/{BRANCH}")


def remote_contains_head() -> bool:
    """Refresh the remote ref and verify whether the local HEAD already landed."""
    try:
        git("fetch", REMOTE, BRANCH)
    except Exception:
        return False
    return git("merge-base", "--is-ancestor", "HEAD", f"{REMOTE}/{BRANCH}", check=False).returncode == 0


def publish_local_commits() -> None:
    """Do not silently idle when prior result commits exist only on this host."""
    ahead_text = git("rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD").stdout.strip()
    ahead = int(ahead_text or "0")
    if ahead == 0:
        return
    print(f"[tct-worker] {ahead} local commit(s) are not on {REMOTE}/{BRANCH}; publishing before queue scan", flush=True)
    try:
        git("push", REMOTE, f"HEAD:{BRANCH}")
    except Exception:
        # GitHub/proxies can accept the pack/ref update and then return an
        # HTTP/RPC error while the client is waiting for the final response.
        # Verify remote state before treating that ambiguous transport failure
        # as a failed publication.
        if remote_contains_head():
            print("[tct-worker] push transport reported failure, but remote contains local HEAD; treating publication as successful", flush=True)
            return
        raise
    git("fetch", REMOTE, BRANCH)


def select_result_artifacts(result_paths: list[Path]) -> tuple[list[Path], list[dict], int]:
    """Select Git-safe result files while keeping oversized raw artifacts local."""
    files: list[Path] = []
    for path in result_paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))

    selected: list[Path] = []
    omitted: list[dict] = []
    total = 0
    seen: set[Path] = set()
    for path in sorted(files):
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        size = path.stat().st_size
        rel = str(path.relative_to(REPO))
        if size > MAX_ARTIFACT_FILE_BYTES:
            omitted.append({"path": rel, "size_bytes": size, "reason": "file_size_limit"})
            continue
        if total + size > MAX_ARTIFACT_TOTAL_BYTES:
            omitted.append({"path": rel, "size_bytes": size, "reason": "total_size_limit"})
            continue
        selected.append(path)
        total += size
    return selected, omitted, total


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
        result_path = RESULTS / f"{job_id}.json"
        if result_path.exists():
            rel = str(result_path.relative_to(REPO))
            tracked = git("ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0
            if tracked:
                continue
            print(
                f"[tct-worker] stale untracked result receipt does not satisfy job {job_id}: {rel}",
                flush=True,
            )
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

    if not RUNTIME_WRAPPER.exists():
        raise RuntimeError(f"runtime wrapper missing: {RUNTIME_WRAPPER}")

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
                ["bash", str(RUNTIME_WRAPPER), str(runner)],
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

    selected_result_files, omitted_result_files, selected_result_bytes = select_result_artifacts(result_paths)

    receipt = {
        "schema_version": 1,
        "job_id": job_id,
        "job_file": str(job_path.relative_to(REPO)),
        "runner": str(runner.relative_to(REPO)),
        "runner_sha256": sha256(runner),
        "runtime_wrapper": str(RUNTIME_WRAPPER.relative_to(REPO)),
        "runtime_wrapper_sha256": sha256(RUNTIME_WRAPPER),
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
        "git_artifact_policy": {
            "max_file_bytes": MAX_ARTIFACT_FILE_BYTES,
            "max_total_bytes": MAX_ARTIFACT_TOTAL_BYTES,
            "selected_result_bytes": selected_result_bytes,
            "selected_result_files": [str(p.relative_to(REPO)) for p in selected_result_files],
            "local_only_omitted_count": len(omitted_result_files),
            "local_only_omitted_files": omitted_result_files[:100],
        },
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }
    write_json(receipt_path, receipt)

    # Stage only compact queue artifacts plus Git-safe declared outputs. Large
    # experimental corpora/checkpoints remain local and are recorded in the
    # receipt instead of being accidentally packed into multi-gigabyte pushes.
    to_add = [job_path, receipt_path, log_path]
    if summary and summary.exists():
        to_add.append(summary)
    to_add.extend(selected_result_files)
    rels = sorted({str(p.relative_to(REPO)) for p in to_add})
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
            if remote_contains_head():
                print(f"[tct-worker] push transport reported failure for {job_id}, but remote contains local HEAD; treating result publication as successful", flush=True)
                return receipt
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
        publish_local_commits()
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
