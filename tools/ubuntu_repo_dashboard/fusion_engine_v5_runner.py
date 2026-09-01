#!/usr/bin/env python3
"""Dashboard runner for Fusion Engine V5."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import pkgutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_PACKAGE = "fusion_engine_v5"
OUT_ROOT = Path("validation_runs/fusion_engine_v5_dashboard")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def package_inventory() -> dict[str, Any]:
    package = importlib.import_module(ROOT_PACKAGE)
    package_path = Path(package.__file__).resolve().parent
    modules = sorted(module.name for module in pkgutil.walk_packages(package.__path__, prefix=f"{ROOT_PACKAGE}."))
    groups: dict[str, int] = {}
    for module in modules:
        parts = module.split(".")
        key = parts[1] if len(parts) > 2 else "root"
        groups[key] = groups.get(key, 0) + 1
    return {
        "package": ROOT_PACKAGE,
        "package_path": str(package_path),
        "module_count": len(modules),
        "groups": dict(sorted(groups.items())),
        "modules": modules,
        "mode": "inventory",
    }


def run_default_simulation() -> dict[str, Any]:
    config = importlib.import_module(f"{ROOT_PACKAGE}.engine.config")
    simulation = importlib.import_module(f"{ROOT_PACKAGE}.engine.reactor_simulation")
    design = dict(config.DEFAULT_DESIGN)
    result = simulation.simulate_reactor(design, blanket_validate=False)
    return {
        "design": json_safe(design),
        "result": json_safe(result),
        "mode": "default_design_simulation",
        "blanket_validate": False,
    }


def write_outputs(payload: dict[str, Any], mode: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUT_ROOT / f"{mode}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": timestamp, "generated_unix": time.time(), **payload}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}

    summary_text = json.dumps(payload, indent=2, sort_keys=True)
    for path in (run_dir / "summary.json", OUT_ROOT / "latest_summary.json"):
        path.write_text(summary_text + "\n", encoding="utf-8")

    lines = [
        "# Fusion Engine V5 Dashboard Run",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- mode: `{payload.get('mode', mode)}`",
        f"- package: `{ROOT_PACKAGE}`",
    ]
    if result:
        lines.extend(
            [
                f"- score: `{result.get('score')}`",
                f"- net_electric: `{result.get('net_electric')}`",
                f"- TBR: `{result.get('TBR')}`",
                f"- fail_rate: `{result.get('fail_rate')}`",
                f"- wall_load: `{result.get('wall_load')}`",
                f"- blanket_model: `{result.get('blanket_model')}`",
                f"- tct_control_strength: `{result.get('tct_control_strength')}`",
            ]
        )
    if "module_count" in payload:
        lines.append(f"- module_count: `{payload.get('module_count')}`")
    report_text = "\n".join(lines) + "\n"
    for path in (run_dir / "report.md", OUT_ROOT / "latest_report.md"):
        path.write_text(report_text, encoding="utf-8")

    metric_rows = []
    if result:
        for key in (
            "score",
            "net_electric",
            "TBR",
            "fail_rate",
            "wall_load",
            "raw_wall_load",
            "bootstrap",
            "wall_temp",
            "capex_billion",
            "tct_control_strength",
        ):
            if key in result:
                metric_rows.append({"metric": key, "value": result[key]})
    else:
        metric_rows.append({"metric": "module_count", "value": payload.get("module_count", 0)})
    for path in (run_dir / "metrics.csv", OUT_ROOT / "latest_metrics.csv"):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerows(metric_rows)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("inventory", "simulate"), required=True)
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    sys.path.insert(0, str(repo))
    if not (repo / ROOT_PACKAGE).is_dir():
        print(f"{ROOT_PACKAGE} is not present in {repo}", file=sys.stderr)
        return 2

    payload = package_inventory() if args.mode == "inventory" else run_default_simulation()
    run_dir = write_outputs(payload, args.mode)
    print(f"wrote {run_dir}")
    print(f"summary: {run_dir / 'summary.json'}")
    print(f"latest: {OUT_ROOT / 'latest_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
