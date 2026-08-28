from __future__ import annotations

import base64
import json
import math
from pathlib import Path
import pickle
import random
import traceback
from typing import Any

from .agent import AgentSupervisor
from .extract import compare_series, extract_series
from .gates import (
    almost_equal_metrics,
    authority_gate,
    physical_lithium_gate,
    reachability_gate,
    sustained_gate,
    topology_gate,
)
from .mechanisms import REGISTRY, crossover, mutate, random_candidate, staged_times, zero_candidate
from .models import Candidate, Evaluation, StageResult
from .objectives import make_objectives, pareto_front
from .runner import M3DRunner
from .state import Store


def _active_window(
    candidate: Candidate, stage: str, cfg: dict[str, Any]
) -> tuple[float, float]:
    # Native ipforce is a standing source with no upstream time gate. For that
    # mechanism family the evaluation starts at t=0. Timed hybrid families still
    # use their magnetic/current-drive gate as the response window.
    if candidate.mechanism == "poloidal_momentum_bias":
        t_on = 0.0
        duration = float(cfg["stages"]["probe_duration"])
        if stage in {"sustained", "full"}:
            duration = 1.0e30
        return t_on, t_on + duration

    if candidate.mechanism in {"staged_magnetic", "staged_mag_momentum"}:
        _t_early, _t_aggressive, _t_hold, t_off = staged_times(candidate.params)
        if stage == "impulse":
            return 0.0, float(cfg["stages"]["probe_duration"])
        return 0.0, t_off

    t_on = float(candidate.params.get("t_on", 0.0))
    duration = float(candidate.params.get("duration", cfg["stages"]["probe_duration"]))
    if stage == "impulse":
        duration = float(cfg["stages"]["probe_duration"])
    return t_on, t_on + duration


class Evaluator:
    def __init__(self, cfg: dict[str, Any], store: Store) -> None:
        self.cfg = cfg
        self.store = store
        self.runner = M3DRunner(cfg)
        self.baseline_cache = {}

    def baseline(self, max_rows: int | None = None):
        key = int(max_rows or -1)
        if key not in self.baseline_cache:
            rows = extract_series(self.cfg["paths"]["baseline_dir"], self.cfg)
            self.baseline_cache[key] = rows if max_rows is None else rows[:max_rows]
        return self.baseline_cache[key]

    def run_stage(self, candidate: Candidate, stage: str) -> StageResult:
        try:
            rc, run_dir, manifest, elapsed = self.runner.execute(candidate, stage)
            result = StageResult(
                stage=stage,
                status="RUN_FAILED" if rc else "RUN_COMPLETE",
                return_code=rc,
                run_dir=str(run_dir),
                input_sha256=manifest["input_sha256"],
                metrics={"elapsed_seconds": elapsed},
            )
            if rc:
                result.error = (
                    (run_dir / "launcher.stderr").read_text(errors="replace")[-4000:]
                    if (run_dir / "launcher.stderr").exists()
                    else ""
                )
                return result

            controlled = extract_series(run_dir, self.cfg)
            baseline = self.baseline(len(controlled))
            t_on, t_off = _active_window(candidate, stage, self.cfg)
            metrics = compare_series(
                baseline,
                controlled,
                t_on,
                t_off,
                response_horizon=float(
                    self.cfg["stages"].get("impulse_response_horizon", 0.05)
                ),
                time_tolerance=float(
                    self.cfg["stages"].get("time_match_tolerance", 1e-9)
                ),
            )
            metrics["elapsed_seconds"] = elapsed
            result.metrics = metrics
            result.gates["reachable"] = reachability_gate(metrics, self.cfg)
            result.gates["authority"] = authority_gate(
                metrics, self.cfg, candidate.mechanism
            )
            if stage in {"sustained", "full"}:
                result.gates["sustained"] = sustained_gate(metrics, self.cfg)
            if stage == "full":
                result.gates["topology"] = topology_gate(metrics, self.cfg)
            return result
        except Exception as exc:
            return StageResult(
                stage=stage,
                status="EXCEPTION",
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-4000:]}",
            )

    def evaluate(self, candidate: Candidate) -> Evaluation:
        evaluation = Evaluation(candidate=candidate)
        impulse = self.run_stage(candidate, "impulse")
        evaluation.stages.append(impulse)
        evaluation.deepest_stage = "impulse"

        if (
            impulse.status == "RUN_COMPLETE"
            and impulse.gates.get("reachable")
            and impulse.gates.get("authority")
        ):
            sustained = self.run_stage(candidate, "sustained")
            evaluation.stages.append(sustained)
            evaluation.deepest_stage = "sustained"

            if sustained.status == "RUN_COMPLETE" and sustained.gates.get("sustained"):
                if self.cfg["search"].get("evaluate_full_topology", True):
                    full = self.run_stage(candidate, "full")
                    evaluation.stages.append(full)
                    evaluation.deepest_stage = "full"
                    evaluation.feasible = bool(
                        full.status == "RUN_COMPLETE"
                        and full.gates.get("sustained")
                        and full.gates.get("topology")
                    )
                else:
                    evaluation.feasible = True

        evaluation.physical_gate = physical_lithium_gate(candidate, self.cfg)
        evaluation.objectives = make_objectives(evaluation)
        return evaluation


def verify_zero(cfg: dict[str, Any]) -> dict[str, Any]:
    store = Store(cfg["paths"]["output_dir"])
    evaluator = Evaluator(cfg, store)
    baseline = evaluator.baseline(int(cfg["stages"]["probe_ntimemax"]) + 1)
    rng = random.Random(0)
    report = {}
    for mechanism in cfg["search"]["enabled_mechanisms"]:
        candidate = zero_candidate(mechanism, rng)
        stage = evaluator.run_stage(candidate, "impulse")
        item = {"candidate": candidate.to_dict(), "stage": stage.to_dict()}
        if stage.status == "RUN_COMPLETE" and stage.run_dir:
            other = extract_series(stage.run_dir, cfg)
            passed, max_delta = almost_equal_metrics(
                baseline[: len(other)],
                other,
                float(cfg["stages"]["zero_abs_tolerance"]),
            )
            item["zero_equivalence_pass"] = passed
            item["max_abs_metric_delta"] = max_delta
        else:
            item["zero_equivalence_pass"] = False
        report[mechanism] = item
    store.write_json("zero_equivalence.json", report)
    return report


def _weighted_mechanism(enabled, weights, rng):
    values = [max(float(weights.get(name, 1.0)), 0.0) for name in enabled]
    if not any(values):
        values = [1.0] * len(enabled)
    return rng.choices(enabled, weights=values, k=1)[0]


def _stats(evaluations):
    out = {}
    for e in evaluations:
        row = out.setdefault(
            e.candidate.mechanism,
            {"count": 0, "impulse_authority": 0, "sustained": 0, "feasible": 0},
        )
        row["count"] += 1
        impulse = e.stage("impulse")
        sustained = e.stage("sustained")
        if impulse and impulse.gates.get("authority"):
            row["impulse_authority"] += 1
        if sustained and sustained.gates.get("sustained"):
            row["sustained"] += 1
        if e.feasible:
            row["feasible"] += 1
    return out


def _rng_dump(rng):
    return base64.b64encode(pickle.dumps(rng.getstate())).decode()


def _rng_load(text):
    return pickle.loads(base64.b64decode(text.encode()))


def search(
    cfg: dict[str, Any],
    population_size: int,
    generations: int,
    seed: int,
    resume: bool = False,
) -> list[Evaluation]:
    enabled = [m for m in cfg["search"]["enabled_mechanisms"] if m in REGISTRY]
    if not enabled:
        raise ValueError("no valid enabled mechanisms")

    store = Store(cfg["paths"]["output_dir"])
    rng = random.Random(seed)
    all_evaluations = store.load_all() if resume else []
    start_generation = 0

    if resume:
        cp = store.read_checkpoint()
        start_generation = int(cp.get("generation", -1)) + 1
        if cp.get("rng_state"):
            rng.setstate(_rng_load(cp["rng_state"]))

    if cfg["search"].get("verify_zero_before_search", True) and not resume:
        zero_report = verify_zero(cfg)
        bad = [
            name
            for name, row in zero_report.items()
            if not row.get("zero_equivalence_pass")
        ]
        if bad:
            raise RuntimeError(f"zero-equivalence failed for mechanism families: {bad}")

    evaluator = Evaluator(cfg, store)
    agent = AgentSupervisor(cfg, Path(cfg["paths"]["output_dir"]))
    current = []

    for generation in range(start_generation, generations):
        front = pareto_front(all_evaluations)
        summary = {
            "generation": generation,
            "mechanism_stats": _stats(all_evaluations),
            "pareto_front": [e.to_dict() for e in front[:20]],
            "allowed_mechanisms": enabled,
            "rule": (
                "Agent may only propose bounded control-layer genomes; "
                "physics keys are immutable. Native ipforce is a standing "
                "flow/shear-bias audit channel. Staged magnetic families are "
                "scheduled open-loop bias/early/aggressive/hold waveforms, not closed-loop feedback."
            ),
        }
        advice = agent.advise(generation, summary)
        weights = advice.get("mechanism_weights", {})
        proposed = agent.validated_proposals(advice, generation)

        if generation == 0 and not current:
            seeded = []
            for proposal in cfg["search"].get("seed_candidates", []):
                try:
                    from .mechanisms import candidate_from_proposal

                    seeded.append(candidate_from_proposal(proposal, generation))
                except Exception:
                    continue
            current = (seeded + proposed)[:population_size]
            while len(current) < population_size:
                current.append(
                    random_candidate(
                        _weighted_mechanism(enabled, weights, rng), rng, generation
                    )
                )
        else:
            front_candidates = [e.candidate for e in front]
            elites_n = max(
                1,
                int(
                    math.ceil(
                        population_size * float(cfg["search"]["elite_fraction"])
                    )
                ),
            )
            parents = (
                front_candidates[: max(elites_n, 1)]
                or [e.candidate for e in all_evaluations[-population_size:]]
            )
            next_population = proposed[:population_size]
            while len(next_population) < population_size:
                if not parents or rng.random() < 0.2:
                    child = random_candidate(
                        _weighted_mechanism(enabled, weights, rng), rng, generation
                    )
                else:
                    parent = rng.choice(parents)
                    child = mutate(
                        parent,
                        rng,
                        float(cfg["search"]["mutation_scale"]),
                        generation,
                    )
                    if (
                        rng.random()
                        < float(cfg["search"]["crossover_probability"])
                        and len(parents) > 1
                    ):
                        mates = [
                            x for x in parents if x.mechanism == child.mechanism
                        ]
                        if mates:
                            child = crossover(
                                child, rng.choice(mates), rng, generation
                            )
                next_population.append(child)
            current = next_population

        seen = {e.candidate.candidate_id for e in all_evaluations}
        for candidate in current:
            if candidate.candidate_id in seen:
                continue
            evaluation = evaluator.evaluate(candidate)
            store.append(evaluation)
            all_evaluations.append(evaluation)
            seen.add(candidate.candidate_id)

        front = pareto_front(all_evaluations)
        store.write_json("pareto_front.json", [e.to_dict() for e in front])
        store.write_json("mechanism_stats.json", _stats(all_evaluations))
        store.write_checkpoint(
            {
                "generation": generation,
                "seed": seed,
                "rng_state": _rng_dump(rng),
                "evaluations": len(all_evaluations),
            }
        )

    return pareto_front(all_evaluations)
