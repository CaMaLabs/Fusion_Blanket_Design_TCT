from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

from .config import load_config, write_default
from .mechanisms import REGISTRY, candidate_updates, random_candidate
from .runner import M3DRunner
from .search import search, verify_zero


def cmd_init(args) -> int:
    write_default(args.output)
    print(args.output)
    return 0


def cmd_dry_run(args) -> int:
    cfg = load_config(args.config)
    rng = random.Random(args.seed)
    enabled = [m for m in cfg["search"]["enabled_mechanisms"] if m in REGISTRY]
    runner = M3DRunner(cfg)
    rows = []
    for i in range(args.count):
        mech = enabled[i % len(enabled)]
        candidate = random_candidate(mech, rng)
        updates = candidate_updates(candidate, "impulse", cfg)
        row = {
            "candidate": candidate.to_dict(),
            "updates": updates,
        }
        if args.prepare:
            run_dir, manifest = runner.prepare(candidate, "impulse")
            row["run_dir"] = str(run_dir)
            row["input_sha256"] = manifest["input_sha256"]
        rows.append(row)
    print(json.dumps(rows, indent=2))
    return 0


def cmd_zero(args) -> int:
    cfg = load_config(args.config)
    report = verify_zero(cfg)
    print(json.dumps(report, indent=2))
    return 0 if all(row.get("zero_equivalence_pass") for row in report.values()) else 2


def cmd_search(args) -> int:
    cfg = load_config(args.config)
    front = search(cfg, args.population, args.generations, args.seed, args.resume)
    print(json.dumps([e.to_dict() for e in front], indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tct-explorer")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("init", help="write a starter JSON config")
    q.add_argument("--output", default="explorer.json")
    q.set_defaults(func=cmd_init)

    q = sub.add_parser("dry-run", help="generate bounded candidates without running M3D-C1")
    q.add_argument("--config", required=True)
    q.add_argument("--count", type=int, default=8)
    q.add_argument("--seed", type=int, default=8776)
    q.add_argument("--prepare", action="store_true", help="also write candidate run directories/C1input")
    q.set_defaults(func=cmd_dry_run)

    q = sub.add_parser("verify-zero", help="run zero-amplitude equivalence for enabled families")
    q.add_argument("--config", required=True)
    q.set_defaults(func=cmd_zero)

    q = sub.add_parser("search", help="run evolutionary mechanism search")
    q.add_argument("--config", required=True)
    q.add_argument("--population", type=int, default=8)
    q.add_argument("--generations", type=int, default=4)
    q.add_argument("--seed", type=int, default=8776)
    q.add_argument("--resume", action="store_true")
    q.set_defaults(func=cmd_search)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
