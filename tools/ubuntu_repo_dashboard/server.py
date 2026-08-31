#!/usr/bin/env python3
"""Dependency-free dashboard for syncing and running whitelisted repo commands."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"


@dataclass
class Job:
    id: str
    action: str
    label: str
    status: str = "queued"
    returncode: int | None = None
    started_at: float | None = None
    ended_at: float | None = None
    log: list[str] = field(default_factory=list)


class DashboardState:
    def __init__(self, repo: Path, remote: str, default_branch: str, token: str | None):
        self.repo = repo
        self.remote = remote
        self.default_branch = default_branch
        self.token = token
        self.lock = threading.Lock()
        self.repo_lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.job_queue: queue.Queue[Job] = queue.Queue()
        self.worker = threading.Thread(target=self._work_loop, daemon=True)
        self.worker.start()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j: j.started_at or 0, reverse=True)
            latest_jobs = [self._job_public(j, tail=40) for j in jobs[:12]]
        return {
            "repo": str(self.repo),
            "remote": self.remote,
            "default_branch": self.default_branch,
            "git": self.git_status(),
            "jobs": latest_jobs,
            "busy": self.repo_lock.locked(),
            "token_required": bool(self.token),
            "actions": action_catalog(self.repo),
        }

    def create_job(self, action: str, branch: str | None = None) -> Job:
        action = action.strip()
        actions = action_catalog(self.repo)
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        job = Job(id=str(uuid.uuid4())[:8], action=action, label=actions[action]["label"])
        if branch:
            job.log.append(f"$ target branch: {branch}")
            job.log.append("")
            job_branch[job.id] = branch
        with self.lock:
            self.jobs[job.id] = job
        self.job_queue.put(job)
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return self._job_public(job, tail=500) if job else None

    def git_status(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ok": False,
            "branch": None,
            "head": None,
            "upstream": None,
            "ahead": None,
            "behind": None,
            "dirty": [],
            "incoming": [],
            "error": None,
        }
        try:
            data["branch"] = run_capture(["git", "branch", "--show-current"], self.repo)
            data["head"] = run_capture(["git", "rev-parse", "--short=12", "HEAD"], self.repo)
            data["upstream"] = run_capture(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], self.repo, check=False)
            data["dirty"] = run_lines(["git", "status", "--short"], self.repo, check=False)[:250]
            if data["upstream"]:
                counts = run_capture(["git", "rev-list", "--left-right", "--count", f"HEAD...{data['upstream']}"], self.repo, check=False)
                parts = counts.split()
                if len(parts) == 2:
                    data["ahead"] = int(parts[0])
                    data["behind"] = int(parts[1])
                data["incoming"] = run_lines(["git", "diff", "--name-status", f"HEAD..{data['upstream']}"], self.repo, check=False)[:200]
            data["ok"] = True
        except Exception as exc:  # noqa: BLE001
            data["error"] = str(exc)
        return data

    def _work_loop(self) -> None:
        while True:
            job = self.job_queue.get()
            try:
                self._run_job(job)
            finally:
                self.job_queue.task_done()

    def _run_job(self, job: Job) -> None:
        with self.repo_lock:
            job.status = "running"
            job.started_at = time.time()
            self._save_job(job)
            try:
                for cmd in commands_for(job.action, self.repo, self.remote, job_branch.pop(job.id, None)):
                    self._append(job, "$ " + shlex.join(cmd))
                    proc = subprocess.Popen(
                        cmd,
                        cwd=self.repo,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        self._append(job, line.rstrip("\n"))
                    rc = proc.wait()
                    self._append(job, f"[exit {rc}]")
                    if rc != 0:
                        job.returncode = rc
                        job.status = "failed"
                        break
                else:
                    job.returncode = 0
                    job.status = "passed"
            except Exception as exc:  # noqa: BLE001
                self._append(job, f"dashboard error: {exc}")
                job.returncode = 1
                job.status = "failed"
            finally:
                job.ended_at = time.time()
                self._save_job(job)

    def _append(self, job: Job, line: str) -> None:
        with self.lock:
            job.log.append(line)
            if len(job.log) > 5000:
                job.log = job.log[-5000:]

    def _save_job(self, job: Job) -> None:
        out_dir = self.repo / ".dashboard_runs"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{job.id}.json").write_text(json.dumps(self._job_public(job, tail=5000), indent=2), encoding="utf-8")

    @staticmethod
    def _job_public(job: Job, tail: int) -> dict[str, Any]:
        payload = asdict(job)
        payload["log"] = job.log[-tail:]
        payload["duration"] = (job.ended_at or time.time()) - job.started_at if job.started_at else None
        return payload


job_branch: dict[str, str] = {}


def run_capture(cmd: list[str], cwd: Path, check: bool = True) -> str:
    result = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{cmd[0]} failed")
    return result.stdout.strip()


def run_lines(cmd: list[str], cwd: Path, check: bool = True) -> list[str]:
    out = run_capture(cmd, cwd, check=check)
    return out.splitlines() if out else []


def action_catalog(repo: Path) -> dict[str, dict[str, str]]:
    actions = {
        "fetch_status": {"label": "Fetch + Inspect", "detail": "Fetch origin and refresh incoming file list."},
        "pull_ff": {"label": "Fast-Forward Pull", "detail": "Fetch and fast-forward the current or selected branch."},
        "smoke": {"label": "Ruzic/Fiflis Smoke", "detail": "Run the liquid lithium smoke script."},
        "tests": {"label": "Repo Tests", "detail": "Run python3 -m pytest -q tests."},
    }
    if (repo / "tools/tct_mechanism_explorer/tests").exists():
        actions["explorer_tests"] = {"label": "Explorer Tests", "detail": "Run tools/tct_mechanism_explorer tests."}
    if (repo / "tools/tct_mechanism_explorer/run_control_v2b.sh").exists():
        actions["control_v2b"] = {"label": "Control V2B", "detail": "Run the M3D-C1 control V2B runner."}
    return actions


def commands_for(action: str, repo: Path, remote: str, branch: str | None) -> list[list[str]]:
    branch_ref = branch or run_capture(["git", "branch", "--show-current"], repo)
    if action == "fetch_status":
        return [["git", "fetch", "--prune", remote]]
    if action == "pull_ff":
        return [["git", "fetch", "--prune", remote], ["git", "checkout", branch_ref], ["git", "pull", "--ff-only", remote, branch_ref]]
    if action == "smoke":
        return [["python3", "liquid_lithium_stability/ruzic_fiflis_2016.py"]]
    if action == "tests":
        return [["python3", "-m", "pytest", "-q", "tests"]]
    if action == "explorer_tests":
        return [["python3", "-m", "pytest", "-q", "tools/tct_mechanism_explorer/tests"]]
    if action == "control_v2b":
        return [["bash", "tools/tct_mechanism_explorer/run_control_v2b.sh"]]
    raise ValueError(f"Unknown action: {action}")


class Handler(SimpleHTTPRequestHandler):
    state: DashboardState

    def translate_path(self, path: str) -> str:
        rel = urlparse(path).path.lstrip("/") or "index.html"
        return str(STATIC_ROOT / rel)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            if not self.authorized():
                self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json(self.state.snapshot())
            return
        if parsed.path == "/api/job":
            if not self.authorized():
                self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            job_id = parse_qs(parsed.query).get("id", [""])[0]
            job = self.state.get_job(job_id)
            if not job:
                self.send_json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(job)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if not self.authorized():
            self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/jobs":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            job = self.state.create_job(str(payload.get("action", "")), payload.get("branch"))
            self.send_json({"job": DashboardState._job_public(job, tail=20)}, HTTPStatus.CREATED)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def authorized(self) -> bool:
        if not self.state.token:
            return True
        return self.headers.get("X-Dashboard-Token") == self.state.token

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("DASHBOARD_REPO", os.getcwd()))
    parser.add_argument("--remote", default=os.environ.get("DASHBOARD_REMOTE", "origin"))
    parser.add_argument("--branch", default=os.environ.get("DASHBOARD_BRANCH", "agent/tct-pulse-train-audit"))
    parser.add_argument("--host", default=os.environ.get("DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DASHBOARD_PORT", "8765")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git repo: {repo}")
    Handler.state = DashboardState(repo=repo, remote=args.remote, default_branch=args.branch, token=os.environ.get("DASHBOARD_TOKEN"))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"dashboard listening on http://{args.host}:{args.port}", flush=True)
    print(f"repo: {repo}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)


if __name__ == "__main__":
    main()
