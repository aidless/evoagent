from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .protocol import Outcome, Run
from .promotion_gate import evaluate_promotion
from .version_registry import VersionRegistry
from .candidate_schema import validate_candidate


@dataclass(frozen=True)
class EvalResult:
    score: float
    passed: int
    total: int
    failures: tuple[str, ...]
    duration_s: float
    outcomes: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "passed": self.passed, "total": self.total,
                "failures": list(self.failures), "duration_s": self.duration_s,
                "outcomes": list(self.outcomes)}



def expand_interpreter(command):
    """Substitute ``{python}`` with the interpreter running evoagent.

    A config that hardcodes a bare ``python`` works on a Windows dev box and
    silently scores 0.0 everywhere else, because every candidate evaluation dies
    with "command not found" and the failure is swallowed into a zero score.
    """
    if not command:
        return command
    return command.replace("{python}", sys.executable)

def canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_id(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(data).encode()).hexdigest()[:12]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def evaluate(root: Path, candidate: dict[str, Any]) -> EvalResult:
    config = load_json(root / "evo.json")
    cases = load_json(root / config["benchmark"])["cases"]
    command = expand_interpreter(config["evaluator_command"])
    timeout = float(config.get("timeout_seconds", 10))
    started = time.monotonic()
    passed, failures, outcomes = 0, [], []
    with tempfile.TemporaryDirectory(prefix="evoagent-") as tmp:
        candidate_path = Path(tmp) / "candidate.json"
        save_json(candidate_path, candidate)
        for case in cases:
            case_started = time.monotonic()
            payload = {}
            env = os.environ.copy()
            env.update({
                "EVO_CANDIDATE": str(candidate_path),
                "EVO_INPUT": json.dumps(case.get("input"), ensure_ascii=False),
                "EVO_EXPECTED": json.dumps(case.get("expected"), ensure_ascii=False),
                "EVO_CASE_ID": str(case.get("id", "unknown")),
            })
            try:
                run = subprocess.run(command, cwd=root, env=env, shell=True, timeout=timeout,
                                     capture_output=True, text=True)
                payload = json.loads(run.stdout.strip()) if run.returncode == 0 else {}
                ok = payload.get("passed") is True
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                ok = False
            case_id = str(case.get("id", "unknown"))
            item_score = float(payload.get("score", 1.0 if ok else 0.0))
            outcomes.append({"task_id": case_id, "passed": ok, "score": max(0.0, min(1.0, item_score)),
                             "cost": max(0.0, float(payload.get("cost", 0.0))),
                             "latency_s": round(time.monotonic() - case_started, 6),
                             "safety_violations": max(0, int(payload.get("safety_violations", 0))),
                             "capabilities": payload.get("capabilities", case.get("capabilities", {})),
                             "details": payload.get("details", {})})
            if ok:
                passed += 1
            else:
                failures.append(str(case.get("id", "unknown")))
    total = len(cases)
    return EvalResult(passed / total if total else 0.0, passed, total, tuple(failures),
                      round(time.monotonic() - started, 4), tuple(outcomes))


def propose(root: Path, incumbent: dict[str, Any], failures: tuple[str, ...]) -> list[dict[str, Any]]:
    config = load_json(root / "evo.json")
    proposer = expand_interpreter(config.get("proposer_command"))
    if proposer:
        env = os.environ.copy()
        env["EVO_INCUMBENT"] = canonical(incumbent)
        env["EVO_FAILURES"] = json.dumps(failures)
        run = subprocess.run(proposer, cwd=root, env=env, shell=True, check=True,
                             capture_output=True, text=True, timeout=config.get("timeout_seconds", 10))
        proposals = json.loads(run.stdout)
        if not isinstance(proposals, list):
            raise ValueError("proposer must output a JSON list")
        return proposals
    proposals = []
    for mutation in config.get("mutations", []):
        candidate = json.loads(canonical(incumbent))
        candidate.update(mutation)
        proposals.append(candidate)
    return proposals


def safety_check(candidate: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    encoded = canonical(candidate)
    if len(encoded) > int(config.get("max_candidate_bytes", 65536)):
        return False, "candidate_too_large"
    lowered = encoded.lower()
    for token in config.get("forbidden_tokens", []):
        if token.lower() in lowered:
            return False, f"forbidden_token:{token}"
    return True, "ok"


def _as_run(run_id: str, cid: str, result: EvalResult) -> Run:
    outcomes = tuple(Outcome(**x) for x in result.outcomes)
    task_hash = hashlib.sha256("\n".join(sorted(x.task_id for x in outcomes)).encode()).hexdigest()
    return Run(run_id, cid, task_hash, outcomes)


def evolve(root: Path) -> dict[str, Any]:
    config = load_json(root / "evo.json")
    state_dir = root / ".evo"
    active_path = state_dir / "active.json"
    incumbent = load_json(active_path)
    baseline = evaluate(root, incumbent)
    records = []
    best, best_result = incumbent, baseline
    for candidate in propose(root, incumbent, baseline.failures):
        safe, reason = safety_check(candidate, config)
        result = evaluate(root, candidate) if safe else EvalResult(0, 0, baseline.total, (reason,), 0)
        records.append({"id": candidate_id(candidate), "candidate": candidate,
                        "safe": safe, "reason": reason, "evaluation": result.as_dict()})
        if safe and result.score > best_result.score:
            best, best_result = candidate, result
    min_gain = float(config.get("min_gain", 0.01))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    legacy_promoted = best_result.score >= baseline.score + min_gain
    gate_cfg = config.get("statistical_gate", {})
    statistical_decision = None
    if gate_cfg.get("enabled") and best is not incumbent:
        statistical_decision = evaluate_promotion(
            _as_run(run_id + "-base", candidate_id(incumbent), baseline),
            _as_run(run_id + "-candidate", candidate_id(best), best_result),
            min_gain=float(gate_cfg.get("min_gain", min_gain)), alpha=float(gate_cfg.get("alpha", 0.05)),
            max_cost_increase=float(gate_cfg.get("max_cost_increase", 0.15)),
            max_latency_increase=float(gate_cfg.get("max_latency_increase", 0.20)),
            max_capability_drop=float(gate_cfg.get("max_capability_drop", 0.01)),
            bootstrap_iterations=int(gate_cfg.get("bootstrap_iterations", 5000)))
        promoted = legacy_promoted and statistical_decision["promote"]
    else:
        promoted = legacy_promoted
    if promoted:
        history = state_dir / "history"
        history.mkdir(parents=True, exist_ok=True)
        shutil.copy2(active_path, history / f"{run_id}-{candidate_id(incumbent)}.json")
        save_json(active_path, best)
        registry = VersionRegistry(state_dir / "version-registry.json")
        vid = candidate_id(best)
        if vid not in registry.data["versions"]:
            registry.register(vid, "agent_strategy", "experimental", {"run_id": run_id})
        registry.transition(vid, "provisional", {"development_passed": True, "rollback_available": True,
                            "statistical_decision": statistical_decision,
              "version_level": "provisional" if promoted else None}, reason="evolve promotion")
    report = {"run_id": run_id, "baseline": baseline.as_dict(), "candidates": records,
              "promoted": promoted, "active_id": candidate_id(best if promoted else incumbent),
              "active_score": best_result.score if promoted else baseline.score,
              "legacy_promoted": legacy_promoted, "statistical_decision": statistical_decision,
              "version_level": "provisional" if promoted else None}
    intelligence_command = expand_interpreter(config.get("post_evolution_intelligence_command"))
    if intelligence_command:
        try:
            check = subprocess.run(intelligence_command, cwd=root, shell=True,
                                   capture_output=True, text=True,
                                   timeout=float(config.get("intelligence_timeout_seconds", 1800)))
            output = check.stdout.strip()
            report["intelligence"] = json.loads(output) if output else {
                "verified": False, "reason": check.stderr.strip() or "no_output"}
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            report["intelligence"] = {"verified": False, "reason": type(exc).__name__}
    save_json(state_dir / "runs" / f"{run_id}.json", report)
    return report


def rollback(root: Path) -> Path:
    history = sorted((root / ".evo" / "history").glob("*.json"), reverse=True)
    if not history:
        raise RuntimeError("no rollback snapshot available")
    active = root / ".evo" / "active.json"
    current = load_json(active)
    chosen = history[0]
    shutil.copy2(chosen, active)
    chosen.unlink()
    save_json(root / ".evo" / "rollback-last.json", {"from": candidate_id(current),
              "to": candidate_id(load_json(active)), "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return active
