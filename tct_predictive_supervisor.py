#!/usr/bin/env python3
"""Evidence-locked predictive supervisor for TCT control studies.

Keeps the existing FAIR-MAST precursor result as the primary trigger:
Mirnov/Mirnov+toroidal. SXR-only stays advisory by default, J/dJdt stays a
reduced-MHD bridge, and NO_ACTION is a first-class output. Event-specific
boosting is allowed only when precursor lead exceeds the latency of an actuator
scenario that already passed the response-budget screen.

This is supervisory/control-policy code, not a measured TCT transfer function.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parent
REVIEW_MANIFEST = REPO / "validation_runs/fair_mast_machine_reviewed_labels_default/fair_mast_machine_reviewed_label_manifest.csv"
ACTUATOR_BUDGET = REPO / "validation_runs/fair_mast_biased_actuator_response_budget_default/fair_mast_biased_actuator_response_budget_summary.json"
TRADEOFF_CSV = REPO / "validation_runs/fair_mast_sxr_precursor_tradeoff_default/fair_mast_sxr_precursor_tradeoff.csv"
DEFAULT_RUN_DIR = REPO / "validation_runs/tct_predictive_supervisor_default"

BRIDGE_SOURCES = {"j", "djdt", "j_djdt"}
SXR_SOURCES = {"sxr", "sxr_only"}
DEFAULT_GUARD_MS = 0.0
DEFAULT_MIN_RISK = 0.5


@dataclass(frozen=True)
class Actuator:
    name: str
    latency_ms: float
    event_specific_allowed: bool
    verdict: str


@dataclass(frozen=True)
class Prediction:
    event_id: str
    lead_ms: float
    risk: float
    confidence: float
    sources: tuple[str, ...]
    target: str = "current_sheet"

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Prediction":
        sources = row.get("sources", [])
        if isinstance(sources, str):
            sources = [s.strip() for s in sources.split(",") if s.strip()]
        return cls(
            event_id=str(row.get("event_id", "prediction")),
            lead_ms=float(row["lead_ms"]),
            risk=float(row.get("risk", 1.0)),
            confidence=float(row.get("confidence", 1.0)),
            sources=tuple(str(s).lower() for s in sources),
            target=str(row.get("target", "current_sheet")),
        )


@dataclass(frozen=True)
class Decision:
    event_id: str
    command: str
    reason: str
    standing_bias: bool
    precursor_class: str
    actuator: str | None
    actuator_latency_ms: float | None
    lead_ms: float
    guard_ms: float
    margin_ms: float | None
    boost_fraction: float
    sources: tuple[str, ...]
    target: str


class PredictiveSupervisor:
    def __init__(
        self,
        actuators: Sequence[Actuator],
        *,
        guard_ms: float = DEFAULT_GUARD_MS,
        min_risk: float = DEFAULT_MIN_RISK,
        standing_bias: bool = True,
        allow_bridge_trigger: bool = False,
        allow_sxr_primary: bool = False,
    ) -> None:
        self.actuators = tuple(actuators)
        self.guard_ms = float(guard_ms)
        self.min_risk = float(min_risk)
        self.standing_bias = standing_bias
        self.allow_bridge_trigger = allow_bridge_trigger
        self.allow_sxr_primary = allow_sxr_primary

    @staticmethod
    def precursor_class(sources: Sequence[str]) -> str:
        src = {s.lower() for s in sources}
        if "mirnov_toroidal" in src or ("mirnov" in src and "toroidal" in src):
            return "mirnov_toroidal"
        if "mirnov" in src:
            return "mirnov"
        if src & BRIDGE_SOURCES:
            return "j_djdt_bridge"
        if src & SXR_SOURCES:
            return "sxr_only"
        return "unqualified"

    def authorize(self, klass: str) -> tuple[bool, str]:
        if klass in {"mirnov", "mirnov_toroidal"}:
            return True, "validated_primary_precursor"
        if klass == "j_djdt_bridge":
            return (
                (True, "explicit_reduced_mhd_bridge")
                if self.allow_bridge_trigger
                else (False, "j_djdt_is_bridge_not_primary")
            )
        if klass == "sxr_only":
            return (
                (True, "explicit_experimental_sxr_override")
                if self.allow_sxr_primary
                else (False, "sxr_only_blocked_by_false_trigger_tradeoff")
            )
        return False, "no_validated_primary_precursor"

    def decide(self, prediction: Prediction) -> Decision:
        klass = self.precursor_class(prediction.sources)
        if not math.isfinite(prediction.lead_ms) or prediction.lead_ms <= 0:
            return self._no_action(prediction, klass, "nonpositive_or_invalid_lead")
        if not math.isfinite(prediction.risk) or prediction.risk < self.min_risk:
            return self._no_action(prediction, klass, "risk_below_threshold")
        if not math.isfinite(prediction.confidence) or prediction.confidence <= 0:
            return self._no_action(prediction, klass, "nonpositive_confidence")

        authorized, reason = self.authorize(klass)
        if not authorized:
            return self._no_action(prediction, klass, reason)

        eligible: list[tuple[float, Actuator]] = []
        for actuator in self.actuators:
            if not actuator.event_specific_allowed:
                continue
            margin = prediction.lead_ms - actuator.latency_ms - self.guard_ms
            if margin > 0:
                eligible.append((margin, actuator))
        if not eligible:
            return self._no_action(
                prediction, klass, "insufficient_lead_for_passing_actuator_plus_guard"
            )

        margin, actuator = min(eligible, key=lambda pair: pair[1].latency_ms)
        boost = min(1.0, max(0.0, prediction.risk * prediction.confidence))
        return Decision(
            event_id=prediction.event_id,
            command="BOUNDED_BOOST",
            reason=reason,
            standing_bias=self.standing_bias,
            precursor_class=klass,
            actuator=actuator.name,
            actuator_latency_ms=actuator.latency_ms,
            lead_ms=prediction.lead_ms,
            guard_ms=self.guard_ms,
            margin_ms=margin,
            boost_fraction=boost,
            sources=prediction.sources,
            target=prediction.target,
        )

    def _no_action(self, p: Prediction, klass: str, reason: str) -> Decision:
        return Decision(
            event_id=p.event_id,
            command="NO_ACTION",
            reason=reason,
            standing_bias=self.standing_bias,
            precursor_class=klass,
            actuator=None,
            actuator_latency_ms=None,
            lead_ms=p.lead_ms,
            guard_ms=self.guard_ms,
            margin_ms=None,
            boost_fraction=0.0,
            sources=p.sources,
            target=p.target,
        )


def load_actuators(path: Path = ACTUATOR_BUDGET) -> list[Actuator]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for row in payload["scenario_rows"]:
        verdict = str(row["verdict"])
        out.append(
            Actuator(
                name=str(row["scenario"]),
                latency_ms=float(row["total_response_ms"]),
                event_specific_allowed=verdict == "passes_for_bounded_boost",
                verdict=verdict,
            )
        )
    return out


def load_reviewed_mirnov(path: Path = REVIEW_MANIFEST) -> tuple[int, list[Prediction]]:
    accepted = 0
    detected: list[Prediction] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("review_label") != "true_elm":
                continue
            accepted += 1
            if row.get("trigger_detected") != "True" or not row.get("lead_ms"):
                continue
            detected.append(
                Prediction(
                    event_id=f"{row['shot']}:{row['event_time_s']}",
                    lead_ms=float(row["lead_ms"]),
                    risk=1.0,
                    confidence=1.0,
                    sources=("mirnov",),
                    target="edge_current_sheet",
                )
            )
    return accepted, detected


def tradeoff_reference(path: Path = TRADEOFF_CSV) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["config_name"] == "mirnov_toroidal" and math.isclose(
                float(row["deadtime_ms"]), 0.35, abs_tol=1e-12
            ):
                return {
                    "detected": int(row["detected"]),
                    "events": int(row["events"]),
                    "false_triggers": int(row["false_triggers"]),
                    "median_lead_ms": float(row["median_lead_ms"]),
                    "reachable_3_ms": int(row["latency_reachable_3_ms"]),
                    "reachable_5_ms": int(row["latency_reachable_5_ms"]),
                }
    raise RuntimeError("Mirnov+toroidal 0.35 ms tradeoff row not found")


def replay(args: argparse.Namespace) -> int:
    actuators = load_actuators(args.actuator_budget)
    supervisor = PredictiveSupervisor(
        actuators,
        guard_ms=args.guard_ms,
        min_risk=args.min_risk,
        allow_bridge_trigger=args.allow_bridge_trigger,
        allow_sxr_primary=args.allow_sxr_primary,
    )
    accepted, predictions = load_reviewed_mirnov(args.review_manifest)
    decisions = [supervisor.decide(p) for p in predictions]
    fired = [d for d in decisions if d.command == "BOUNDED_BOOST"]

    summary = {
        "status": "TCT_PREDICTIVE_SUPERVISOR_REPLAY_COMPLETED",
        "accepted_true_elm_count": accepted,
        "mirnov_detected_count": len(predictions),
        "bounded_boost_count": len(fired),
        "no_action_count": len(decisions) - len(fired),
        "guard_ms": args.guard_ms,
        "actuator_counts": {
            name: sum(d.actuator == name for d in fired)
            for name in sorted({d.actuator for d in fired if d.actuator})
        },
        "mirnov_toroidal_reference": tradeoff_reference(args.tradeoff_csv),
        "claim_boundary": (
            "Supervisor/latency replay only; no measured TCT actuator transfer "
            "function and no causal plasma-suppression claim."
        ),
    }

    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "tct_predictive_supervisor_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.run_dir / "tct_predictive_supervisor_decisions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fields = list(asdict(decisions[0])) if decisions else ["event_id", "command"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for decision in decisions:
            row = asdict(decision)
            row["sources"] = ",".join(decision.sources)
            writer.writerow(row)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def decide_one(args: argparse.Namespace) -> int:
    payload = (
        json.load(__import__("sys").stdin)
        if args.input == "-"
        else json.loads(Path(args.input).read_text(encoding="utf-8"))
    )
    supervisor = PredictiveSupervisor(
        load_actuators(args.actuator_budget),
        guard_ms=args.guard_ms,
        min_risk=args.min_risk,
        allow_bridge_trigger=args.allow_bridge_trigger,
        allow_sxr_primary=args.allow_sxr_primary,
    )
    print(json.dumps(asdict(supervisor.decide(Prediction.from_dict(payload))), indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--actuator-budget", type=Path, default=ACTUATOR_BUDGET)
        p.add_argument("--guard-ms", type=float, default=DEFAULT_GUARD_MS)
        p.add_argument("--min-risk", type=float, default=DEFAULT_MIN_RISK)
        p.add_argument("--allow-bridge-trigger", action="store_true")
        p.add_argument("--allow-sxr-primary", action="store_true")

    p_replay = sub.add_parser("replay")
    common(p_replay)
    p_replay.add_argument("--review-manifest", type=Path, default=REVIEW_MANIFEST)
    p_replay.add_argument("--tradeoff-csv", type=Path, default=TRADEOFF_CSV)
    p_replay.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    p_replay.set_defaults(func=replay)

    p_decide = sub.add_parser("decide")
    common(p_decide)
    p_decide.add_argument("--input", default="-")
    p_decide.set_defaults(func=decide_one)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
