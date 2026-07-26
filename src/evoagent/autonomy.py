from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .core import EvalResult, candidate_id, load_json, save_json, safety_check
from .promotion_gate import evaluate_promotion
from .protocol import Outcome, Run
from .version_registry import VersionRegistry
from .experience import ExperienceStore, diagnose

Evaluator = Callable[[Path, dict[str, Any]], EvalResult]
Proposer = Callable[[Path, dict[str, Any], tuple[str, ...]], list[dict[str, Any]]]


@dataclass(frozen=True)
class EvolutionPolicy:
    max_rounds: int = 3
    max_candidates_per_round: int = 12
    patience: int = 1
    min_gain: float = 0.01
    require_statistical_gate: bool = True
    allow_revisit: bool = False

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "EvolutionPolicy":
        raw = config.get("autonomy", {})
        gate = config.get("statistical_gate", {})
        return cls(
            max_rounds=max(1, int(raw.get("max_rounds", 3))),
            max_candidates_per_round=max(
                1, int(raw.get("max_candidates_per_round", 12))
            ),
            patience=max(1, int(raw.get("patience", 1))),
            min_gain=float(raw.get("min_gain", config.get("min_gain", 0.01))),
            require_statistical_gate=bool(
                raw.get("require_statistical_gate", gate.get("enabled", True))
            ),
            allow_revisit=bool(raw.get("allow_revisit", False)),
        )


@dataclass(frozen=True)
class EvolutionResult:
    report: dict[str, Any]
    report_path: Path


def _task_set_hash(result: EvalResult) -> str:
    ids = sorted(str(row["task_id"]) for row in result.outcomes)
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def _as_run(run_id: str, cid: str, result: EvalResult) -> Run:
    return Run(
        run_id,
        cid,
        _task_set_hash(result),
        tuple(Outcome(**row) for row in result.outcomes),
    )


def _gate(
    config: dict[str, Any],
    run_id: str,
    baseline_id: str,
    baseline: EvalResult,
    candidate: dict[str, Any],
    result: EvalResult,
) -> dict[str, Any]:
    gate_cfg = config.get("statistical_gate", {})
    if not gate_cfg.get("enabled", True):
        gain = result.score - baseline.score
        return {
            "promote": gain >= float(config.get("min_gain", 0.01)),
            "reasons": [] if gain >= float(config.get("min_gain", 0.01)) else ["gain_below_threshold"],
            "mean_gain": gain,
            "mode": "score_only",
        }
    return evaluate_promotion(
        _as_run(run_id + "-base", baseline_id, baseline),
        _as_run(run_id + "-candidate", candidate_id(candidate), result),
        min_gain=float(gate_cfg.get("min_gain", config.get("min_gain", 0.01))),
        alpha=float(gate_cfg.get("alpha", 0.05)),
        max_cost_increase=float(gate_cfg.get("max_cost_increase", 0.15)),
        max_latency_increase=float(gate_cfg.get("max_latency_increase", 0.20)),
        max_capability_drop=float(gate_cfg.get("max_capability_drop", 0.01)),
        bootstrap_iterations=int(gate_cfg.get("bootstrap_iterations", 5000)),
    )


def _persist_candidate(
    state_dir: Path,
    cid: str,
    candidate: dict[str, Any],
    evaluation: EvalResult,
) -> Path:
    path = state_dir / "candidates" / f"{cid}.json"
    save_json(
        path,
        {"candidate_id": cid, "candidate": candidate, "evaluation": evaluation.as_dict()},
    )
    return path


def _promote(
    root: Path,
    run_id: str,
    incumbent: dict[str, Any],
    winner: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    state_dir = root / ".evo"
    active_path = state_dir / "active.json"
    history = state_dir / "history"
    history.mkdir(parents=True, exist_ok=True)
    shutil.copy2(active_path, history / f"{run_id}-{candidate_id(incumbent)}.json")
    save_json(active_path, winner)
    registry = VersionRegistry(state_dir / "version-registry.json")
    version_id = candidate_id(winner)
    if version_id not in registry.data["versions"]:
        registry.register(
            version_id,
            "agent_strategy",
            "experimental",
            {"run_id": run_id, "decision": decision},
        )
    registry.transition(
        version_id,
        "provisional",
        {
            "development_passed": True,
            "rollback_available": True,
            "statistical_decision": decision,
        },
        reason="autonomous evolution promotion",
    )


def evolve_autonomously(
    root: Path,
    evaluator: Evaluator,
    proposer: Proposer,
    policy: EvolutionPolicy | None = None,
) -> EvolutionResult:
    """Run a bounded, auditable propose/evaluate/select/promote learning loop.

    Evaluation and proposal are dependency-injected, so the same controller can
    evolve prompts, routing policies, tools, model adapters, or workflow bundles.
    Only immutable JSON candidates cross the controller boundary.
    """
    root = root.resolve()
    config = load_json(root / "evo.json")
    policy = policy or EvolutionPolicy.from_config(config)
    state_dir = root / ".evo"
    active_path = state_dir / "active.json"
    incumbent = load_json(active_path)
    incumbent_id = candidate_id(incumbent)
    baseline = evaluator(root, incumbent)
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1_000_000:06d}"
    started = time.monotonic()
    seen = {incumbent_id}
    experience = ExperienceStore(state_dir / "experience.json")
    baseline_diagnosis = diagnose(baseline).as_dict()
    experience_before = experience.summary()
    rounds: list[dict[str, Any]] = []
    best_candidate = incumbent
    best_result = baseline
    best_decision: dict[str, Any] | None = None
    eligible_candidate: dict[str, Any] | None = None
    eligible_result: EvalResult | None = None
    eligible_decision: dict[str, Any] | None = None
    no_improvement = 0
    stop_reason = "max_rounds"

    for round_number in range(1, policy.max_rounds + 1):
        round_parent = best_candidate
        round_parent_result = best_result
        failures = round_parent_result.failures
        proposals = proposer(root, round_parent, failures)
        if not isinstance(proposals, list):
            raise ValueError("proposer must return a list")
        records = []
        round_improved = False
        for candidate in proposals[: policy.max_candidates_per_round]:
            if not isinstance(candidate, dict):
                records.append({"status": "invalid_candidate", "reason": "not_an_object"})
                continue
            cid = candidate_id(candidate)
            if cid in seen and not policy.allow_revisit:
                records.append({"candidate_id": cid, "status": "duplicate"})
                continue
            seen.add(cid)
            safe, reason = safety_check(candidate, config)
            if not safe:
                records.append(
                    {"candidate_id": cid, "status": "rejected", "reason": reason}
                )
                continue
            evaluation = evaluator(root, candidate)
            artifact = _persist_candidate(state_dir, cid, candidate, evaluation)
            decision = _gate(
                config,
                run_id,
                incumbent_id,
                baseline,
                candidate,
                evaluation,
            )
            record = {
                "candidate_id": cid,
                "status": "evaluated",
                "score": evaluation.score,
                "gain_over_active": evaluation.score - baseline.score,
                "failures": list(evaluation.failures),
                "decision": decision,
                "artifact": str(artifact),
            }
            records.append(record)
            experience.record(
                run_id, round_parent, candidate, round_parent_result, evaluation, decision
            )
            if decision.get("promote") and (
                eligible_result is None or evaluation.score > eligible_result.score
            ):
                eligible_candidate = candidate
                eligible_result = evaluation
                eligible_decision = decision
            if evaluation.score > best_result.score:
                best_candidate = candidate
                best_result = evaluation
                best_decision = decision
                round_improved = True
        rounds.append(
            {
                "round": round_number,
                "input_candidate_id": candidate_id(best_candidate),
                "proposed": len(proposals),
                "candidates": records,
                "improved": round_improved,
            }
        )
        if round_improved:
            no_improvement = 0
        else:
            no_improvement += 1
        if no_improvement >= policy.patience:
            stop_reason = "patience_exhausted"
            break

    observed_gain = best_result.score - baseline.score
    if policy.require_statistical_gate:
        selected_candidate = eligible_candidate
        selected_result = eligible_result
        selected_decision = eligible_decision
    else:
        selected_candidate = best_candidate if best_candidate is not incumbent else None
        selected_result = best_result if selected_candidate is not None else None
        selected_decision = best_decision
    gain = selected_result.score - baseline.score if selected_result else observed_gain
    score_passed = selected_result is not None and gain >= policy.min_gain
    promoted = bool(selected_candidate is not None and score_passed)
    if promoted:
        _promote(root, run_id, incumbent, selected_candidate, selected_decision or {})
        experience.mark_promoted(run_id, candidate_id(selected_candidate))
    elif best_candidate is incumbent:
        stop_reason = "no_improving_candidate"
    elif policy.require_statistical_gate and eligible_candidate is None:
        stop_reason = "promotion_gate_rejected"
    elif not score_passed:
        stop_reason = "gain_below_threshold"

    report = {
        "schema_version": 1,
        "run_id": run_id,
        "controller": "bounded-autonomous-v1",
        "started_from": incumbent_id,
        "active_id": candidate_id(selected_candidate if promoted else incumbent),
        "promoted": promoted,
        "stop_reason": stop_reason,
        "baseline": baseline.as_dict(),
        "baseline_diagnosis": baseline_diagnosis,
        "experience": {"before": experience_before, "after": experience.summary()},
        "best_observed": {
            "candidate_id": candidate_id(best_candidate),
            "evaluation": best_result.as_dict(),
            "gain": observed_gain,
            "decision": best_decision,
        },
        "winner": {
            "candidate_id": candidate_id(selected_candidate) if selected_candidate else None,
            "evaluation": selected_result.as_dict() if selected_result else None,
            "gain": gain if selected_result else None,
            "decision": selected_decision,
        },
        "rounds": rounds,
        "seen_candidates": len(seen),
        "duration_s": round(time.monotonic() - started, 4),
        "policy": {
            "max_rounds": policy.max_rounds,
            "max_candidates_per_round": policy.max_candidates_per_round,
            "patience": policy.patience,
            "min_gain": policy.min_gain,
            "require_statistical_gate": policy.require_statistical_gate,
            "allow_revisit": policy.allow_revisit,
        },
    }
    report_path = state_dir / "autonomy" / f"{run_id}.json"
    save_json(report_path, report)
    save_json(state_dir / "autonomy-last.json", report)
    return EvolutionResult(report, report_path)
