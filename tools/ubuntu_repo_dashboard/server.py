#!/usr/bin/env python3
"""Dependency-free dashboard for syncing and running whitelisted repo commands."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
DEFAULT_RESULT_PATHS = (
    "validation_runs/",
    "validation_models/",
    "explorer_run.log",
    "tools/tct_mechanism_explorer/explorer.json",
)
FUSION_ENGINE_PACKAGE = "fusion_engine_v5"
FUSION_ENGINE_OUT = "validation_runs/fusion_engine_v5_dashboard"


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
    def __init__(
        self,
        repo: Path,
        app_repo: Path,
        remote: str,
        default_branch: str,
        self_branch: str,
        token: str | None,
        auto_fetch_interval: int,
        auto_self_update_interval: int,
        auto_push: bool,
        result_paths: tuple[str, ...],
    ):
        self.repo = repo
        self.app_repo = app_repo
        self.remote = remote
        self.default_branch = default_branch
        self.self_branch = self_branch
        self.token = token
        self.auto_fetch_interval = auto_fetch_interval
        self.auto_self_update_interval = auto_self_update_interval
        self.auto_push = auto_push
        self.result_paths = result_paths
        self.remote_branches: list[str] = []
        self.last_auto_fetch: float | None = None
        self.last_auto_fetch_error: str | None = None
        self.last_self_update: float | None = None
        self.last_self_update_error: str | None = None
        self.lock = threading.Lock()
        self.repo_lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.job_queue: queue.Queue[Job] = queue.Queue()
        self.worker = threading.Thread(target=self._work_loop, daemon=True)
        self.background = threading.Thread(target=self._background_loop, daemon=True)
        self.worker.start()
        self.background.start()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j: j.started_at or 0, reverse=True)
            latest_jobs = [self._job_public(j, tail=40) for j in jobs[:12]]
            remote_branches = list(self.remote_branches)
            last_fetch = self.last_auto_fetch
            fetch_error = self.last_auto_fetch_error
            last_self_update = self.last_self_update
            self_update_error = self.last_self_update_error
        return {
            "repo": str(self.repo),
            "app_repo": str(self.app_repo),
            "remote": self.remote,
            "default_branch": self.default_branch,
            "self_branch": self.self_branch,
            "git": self.git_status(),
            "jobs": latest_jobs,
            "busy": self.repo_lock.locked(),
            "token_required": bool(self.token),
            "actions": action_catalog(self.repo),
            "fusion_engine_v5": fusion_engine_status(self.repo),
            "remote_branches": remote_branches,
            "auto_fetch_interval": self.auto_fetch_interval,
            "auto_push": self.auto_push,
            "result_paths": list(self.result_paths),
            "result_files": list_result_files(self.repo, self.result_paths, limit=80),
            "last_auto_fetch": last_fetch,
            "last_auto_fetch_error": fetch_error,
            "auto_self_update_interval": self.auto_self_update_interval,
            "last_self_update": last_self_update,
            "last_self_update_error": self_update_error,
        }

    def create_job(self, action: str, branch: str | None = None) -> Job:
        action = action.strip()
        actions = action_catalog(self.repo)
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        job = Job(id=str(uuid.uuid4())[:8], action=action, label=actions[action]["label"])
        if action == "self_update":
            branch = self.self_branch
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
            before_status = status_map(self.repo)
            try:
                branch = job_branch.pop(job.id, None)
                for cwd, cmd in self.commands_for_job(job.action, branch):
                    self._append(job, "$ " + shlex.join(cmd))
                    proc = subprocess.Popen(
                        cmd,
                        cwd=cwd,
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
                if job.status == "passed" and job.action in runnable_actions(self.repo) and self.auto_push:
                    self._auto_push_results(job, before_status)
            except Exception as exc:  # noqa: BLE001
                self._append(job, f"dashboard error: {exc}")
                job.returncode = 1
                job.status = "failed"
            finally:
                job.ended_at = time.time()
                self._save_job(job)
                if job.status == "passed" and job.action == "self_update":
                    self._append(job, "self update complete; restarting dashboard process")
                    self._save_job(job)
                    threading.Thread(target=restart_process, daemon=True).start()

    def _auto_push_results(self, job: Job, before_status: dict[str, str]) -> None:
        after_status = status_map(self.repo)
        candidates = result_candidates(before_status, after_status, self.result_paths)
        if not candidates:
            self._append(job, "auto-push: no new result files to publish")
            return
        branch = run_capture(["git", "branch", "--show-current"], self.repo, check=False)
        if not branch:
            self._append(job, "auto-push: skipped because HEAD is detached")
            return
        self._append(job, "auto-push: staging result files")
        for path in candidates:
            self._run_logged(job, ["git", "add", "--", path])
        if run_rc(["git", "diff", "--cached", "--quiet"], self.repo) == 0:
            self._append(job, "auto-push: no staged result delta after filtering")
            return
        message = f"Publish dashboard results for {job.label} ({job.id})"
        if self._run_logged(job, ["git", "commit", "-m", message]) != 0:
            return
        self._run_logged(job, ["git", "push", self.remote, f"HEAD:{branch}"])

    def _run_logged(self, job: Job, cmd: list[str]) -> int:
        self._append(job, "$ " + shlex.join(cmd))
        result = subprocess.run(cmd, cwd=self.repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if result.stdout:
            for line in result.stdout.rstrip("\n").splitlines():
                self._append(job, line)
        self._append(job, f"[exit {result.returncode}]")
        return result.returncode

    def _background_loop(self) -> None:
        last_fetch = 0.0
        last_self_update = 0.0
        while True:
            now = time.time()
            if self.auto_fetch_interval > 0 and now - last_fetch >= self.auto_fetch_interval:
                self._background_fetch()
                last_fetch = now
            if self.auto_self_update_interval > 0 and now - last_self_update >= self.auto_self_update_interval:
                self._background_self_update()
                last_self_update = now
            time.sleep(5)

    def _background_fetch(self) -> None:
        if self.repo_lock.locked():
            return
        with self.repo_lock:
            try:
                subprocess.run(["git", "fetch", "--prune", self.remote], cwd=self.repo, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
                branches = remote_branches(self.repo, self.remote)
                with self.lock:
                    self.remote_branches = branches
                    self.last_auto_fetch = time.time()
                    self.last_auto_fetch_error = None
            except Exception as exc:  # noqa: BLE001
                with self.lock:
                    self.last_auto_fetch = time.time()
                    self.last_auto_fetch_error = str(exc)

    def _background_self_update(self) -> None:
        if self.repo_lock.locked():
            return
        branch = run_capture(["git", "branch", "--show-current"], self.app_repo, check=False)
        if branch != self.self_branch:
            return
        with self.repo_lock:
            try:
                subprocess.run(["git", "fetch", "--prune", self.remote, self.self_branch], cwd=self.app_repo, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
                before = run_capture(["git", "rev-parse", "HEAD"], self.app_repo)
                subprocess.run(["git", "pull", "--ff-only", self.remote, self.self_branch], cwd=self.app_repo, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
                after = run_capture(["git", "rev-parse", "HEAD"], self.app_repo)
                with self.lock:
                    self.last_self_update = time.time()
                    self.last_self_update_error = None
                if before != after:
                    restart_process()
            except Exception as exc:  # noqa: BLE001
                with self.lock:
                    self.last_self_update = time.time()
                    self.last_self_update_error = str(exc)

    def commands_for_job(self, action: str, branch: str | None) -> list[tuple[Path, list[str]]]:
        if action == "self_update":
            return [(self.app_repo, cmd) for cmd in commands_for(action, self.app_repo, self.remote, self.self_branch)]
        return [(self.repo, cmd) for cmd in commands_for(action, self.repo, self.remote, branch)]

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


def run_git_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"could not find app git repo from {path}")
    return Path(result.stdout.strip()).resolve()


def run_rc(cmd: list[str], cwd: Path) -> int:
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode


def status_map(repo: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in run_lines(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo, check=False):
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries[path] = line[:2]
    return entries


def remote_branches(repo: Path, remote: str) -> list[str]:
    prefix = f"{remote}/"
    branches: list[str] = []
    for line in run_lines(["git", "for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}"], repo, check=False):
        if line == f"{remote}/HEAD" or not line.startswith(prefix):
            continue
        branches.append(line.removeprefix(prefix))
    return sorted(set(branches))


def result_candidates(before: dict[str, str], after: dict[str, str], allowed_prefixes: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    for path, state in sorted(after.items()):
        if path in before:
            continue
        if state.strip().startswith("D"):
            continue
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allowed_prefixes):
            candidates.append(path)
    return candidates


def is_allowed_result_path(path: str, allowed_prefixes: tuple[str, ...]) -> bool:
    clean = path.strip().lstrip("/")
    if not clean or clean.startswith("../") or "/../" in clean:
        return False
    return any(clean == prefix.rstrip("/") or clean.startswith(prefix) for prefix in allowed_prefixes)


def resolved_result_path(repo: Path, rel_path: str, allowed_prefixes: tuple[str, ...]) -> Path:
    if not is_allowed_result_path(rel_path, allowed_prefixes):
        raise ValueError("path is outside configured result paths")
    target = (repo / rel_path).resolve()
    repo_root = repo.resolve()
    if repo_root not in target.parents and target != repo_root:
        raise ValueError("path escapes repository")
    if not target.is_file():
        raise FileNotFoundError(rel_path)
    return target


def list_result_files(repo: Path, allowed_prefixes: tuple[str, ...], limit: int = 200) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for prefix in allowed_prefixes:
        root = repo / prefix
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = [path for path in root.rglob("*") if path.is_file()]
        else:
            continue
        for path in candidates:
            try:
                stat = path.stat()
                rel = path.relative_to(repo).as_posix()
            except OSError:
                continue
            files.append(
                {
                    "path": rel,
                    "name": path.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "download_url": "/api/download?path=" + quote(rel),
                }
            )
    files.sort(key=lambda item: item["mtime"], reverse=True)
    return files[:limit]


def fusion_engine_status(repo: Path) -> dict[str, Any]:
    package_dir = repo / FUSION_ENGINE_PACKAGE
    out_dir = repo / FUSION_ENGINE_OUT
    latest_summary = out_dir / "latest_summary.json"
    data: dict[str, Any] = {
        "present": package_dir.is_dir(),
        "package_path": str(package_dir) if package_dir.exists() else None,
        "latest_summary": None,
        "latest_report": f"{FUSION_ENGINE_OUT}/latest_report.md" if (out_dir / "latest_report.md").is_file() else None,
        "latest_metrics": {},
        "error": None,
    }
    if not latest_summary.is_file():
        return data
    try:
        payload = json.loads(latest_summary.read_text(encoding="utf-8"))
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        data["latest_summary"] = f"{FUSION_ENGINE_OUT}/latest_summary.json"
        data["latest_metrics"] = {
            key: result.get(key)
            for key in (
                "score",
                "net_electric",
                "TBR",
                "fail_rate",
                "wall_load",
                "blanket_model",
                "tct_control_strength",
            )
            if key in result
        }
        data["generated_at"] = payload.get("generated_at")
        data["mode"] = payload.get("mode")
    except Exception as exc:  # noqa: BLE001
        data["error"] = str(exc)
    return data


def runnable_actions(repo: Path) -> set[str]:
    return set(action_catalog(repo)) - {"fetch_status", "pull_ff", "self_update"}


def action_catalog(repo: Path) -> dict[str, dict[str, str]]:
    actions = {
        "fetch_status": {"label": "Fetch + Inspect", "detail": "Fetch origin and refresh incoming file list."},
        "pull_ff": {"label": "Fast-Forward Pull", "detail": "Fetch and fast-forward the current or selected branch."},
        "self_update": {"label": "Self Update", "detail": "Pull the dashboard branch and restart the process."},
        "smoke": {"label": "Ruzic/Fiflis Smoke", "detail": "Run the liquid lithium smoke script."},
        "tests": {"label": "Repo Tests", "detail": "Run python3 -m pytest -q tests."},
    }
    if (repo / "tools/tct_mechanism_explorer/tests").exists():
        actions["explorer_tests"] = {"label": "Explorer Tests", "detail": "Run tools/tct_mechanism_explorer tests."}
    if (repo / "tools/tct_mechanism_explorer/run_control_v2b.sh").exists():
        actions["control_v2b"] = {"label": "Control V2B", "detail": "Run the M3D-C1 control V2B runner."}
    if (repo / FUSION_ENGINE_PACKAGE).is_dir():
        actions["fusion_v5_inventory"] = {"label": "Fusion V5 Inventory", "detail": "Map Fusion Engine V5 modules and write a dashboard result."}
        actions["fusion_v5_simulate"] = {"label": "Fusion V5 Simulate", "detail": "Run Fusion Engine V5 DEFAULT_DESIGN simulation and publish metrics."}
    return actions


def commands_for(action: str, repo: Path, remote: str, branch: str | None) -> list[list[str]]:
    branch_ref = branch or run_capture(["git", "branch", "--show-current"], repo)
    if action == "fetch_status":
        return [["git", "fetch", "--prune", remote]]
    if action == "pull_ff":
        return [["git", "fetch", "--prune", remote], *checkout_commands(repo, remote, branch_ref), ["git", "pull", "--ff-only", remote, branch_ref]]
    if action == "self_update":
        return [["git", "fetch", "--prune", remote, branch_ref], *checkout_commands(repo, remote, branch_ref), ["git", "pull", "--ff-only", remote, branch_ref]]
    if action == "smoke":
        return [["python3", "liquid_lithium_stability/ruzic_fiflis_2016.py"]]
    if action == "tests":
        return [["python3", "-m", "pytest", "-q", "tests"]]
    if action == "explorer_tests":
        return [["python3", "-m", "pytest", "-q", "tools/tct_mechanism_explorer/tests"]]
    if action == "control_v2b":
        return [["bash", "tools/tct_mechanism_explorer/run_control_v2b.sh"]]
    if action == "fusion_v5_inventory":
        return [["python3", str(ROOT / "fusion_engine_v5_runner.py"), "--mode", "inventory"]]
    if action == "fusion_v5_simulate":
        return [["python3", str(ROOT / "fusion_engine_v5_runner.py"), "--mode", "simulate"]]
    raise ValueError(f"Unknown action: {action}")


def checkout_commands(repo: Path, remote: str, branch: str) -> list[list[str]]:
    local_branches = set(run_lines(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], repo, check=False))
    if branch in local_branches:
        return [["git", "checkout", branch]]
    remote_name = f"{remote}/{branch}"
    remote_set = set(run_lines(["git", "for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}"], repo, check=False))
    if remote_name in remote_set:
        return [["git", "checkout", "--track", remote_name]]
    return [["git", "checkout", branch]]


def restart_process() -> None:
    time.sleep(0.5)
    os.execv(sys.executable, [sys.executable, *sys.argv])


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
        if parsed.path == "/api/files":
            if not self.authorized():
                self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"files": list_result_files(self.state.repo, self.state.result_paths, limit=500)})
            return
        if parsed.path == "/api/download":
            if not self.authorized():
                self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            rel_path = parse_qs(parsed.query).get("path", [""])[0]
            try:
                target = resolved_result_path(self.state.repo, rel_path, self.state.result_paths)
                data = target.read_bytes()
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                safe_name = target.name.replace('"', "")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_json({"error": "file not found"}, HTTPStatus.NOT_FOUND)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
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
    parser.add_argument("--app-repo", default=os.environ.get("DASHBOARD_APP_REPO"))
    parser.add_argument("--remote", default=os.environ.get("DASHBOARD_REMOTE", "origin"))
    parser.add_argument("--branch", default=os.environ.get("DASHBOARD_BRANCH", "agent/tct-pulse-train-audit"))
    parser.add_argument("--self-branch", default=os.environ.get("DASHBOARD_SELF_BRANCH", "agent/ubuntu-repo-dashboard"))
    parser.add_argument("--host", default=os.environ.get("DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DASHBOARD_PORT", "8765")))
    parser.add_argument("--auto-fetch-interval", type=int, default=int(os.environ.get("DASHBOARD_AUTO_FETCH_INTERVAL", "60")))
    parser.add_argument("--auto-self-update-interval", type=int, default=int(os.environ.get("DASHBOARD_AUTO_SELF_UPDATE_INTERVAL", "0")))
    parser.add_argument("--no-auto-push", action="store_true", default=os.environ.get("DASHBOARD_AUTO_PUSH", "1") == "0")
    parser.add_argument("--result-path", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git repo: {repo}")
    app_repo = Path(args.app_repo).resolve() if args.app_repo else run_git_root(ROOT)
    if not (app_repo / ".git").exists():
        raise SystemExit(f"not a git app repo: {app_repo}")
    result_paths = tuple(args.result_path or DEFAULT_RESULT_PATHS)
    Handler.state = DashboardState(
        repo=repo,
        app_repo=app_repo,
        remote=args.remote,
        default_branch=args.branch,
        self_branch=args.self_branch,
        token=os.environ.get("DASHBOARD_TOKEN"),
        auto_fetch_interval=max(0, args.auto_fetch_interval),
        auto_self_update_interval=max(0, args.auto_self_update_interval),
        auto_push=not args.no_auto_push,
        result_paths=result_paths,
    )
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"dashboard listening on http://{args.host}:{args.port}", flush=True)
    print(f"repo: {repo}", flush=True)
    print(f"app repo: {app_repo}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)


if __name__ == "__main__":
    main()
