from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .active_binding import build_active_binding
from .candidate_schema import validate_candidate
from .core import candidate_id, load_json, save_json
from .stage_gates import FourStagePolicy, StageEvidence, evaluate_four_stage, write_decision
from .version_registry import VersionRegistry

StageRunner = Callable[[str, dict, dict], StageEvidence]
HealthCheck = Callable[[dict], dict]
BundleVerifier = Callable[[str], dict]


@dataclass(frozen=True)
class L3Policy:
    max_cost: float = 10.0
    max_latency_s: float = 300.0
    max_safety_violations: int = 0
    dry_run: bool = True
    require_stage_artifacts: bool = True
    require_real_execution: bool = True
    require_bundle_binding: bool = True
    require_valid_bundle: bool = True


def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("l3_run_already_active")
    os.write(fd, str(os.getpid()).encode())
    return fd


def _unlock(path: Path, fd: int):
    os.close(fd)
    path.unlink(missing_ok=True)


def _metrics(evidence: list[StageEvidence]):
    cost = sum(float(item.decision.get("cost", 0.0)) for item in evidence)
    latency = sum(float(item.decision.get("latency_s", 0.0)) for item in evidence)
    safety = sum(item.safety_violations for item in evidence)
    return {"cost": cost, "latency_s": latency, "safety_violations": safety}


def run_l3_provisional(
    root: Path,
    candidate: dict,
    runner: StageRunner,
    health_check: HealthCheck | None = None,
    policy: L3Policy | None = None,
    bundle: dict | None = None,
    bundle_verifier: BundleVerifier | None = None,
) -> dict:
    root = root.resolve()
    policy = policy or L3Policy()
    state = root / ".evo"
    lock_path = state / "locks" / "l3.lock"
    fd = _lock(lock_path)
    txid = f"l3-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    active_path = state / "active.json"
    binding_path = state / "active-binding.json"
    baseline = load_json(active_path)
    previous_binding = load_json(binding_path) if binding_path.exists() else None
    cid = candidate_id(candidate)
    bid = candidate_id(baseline)
    snapshot = state / "transactions" / f"{txid}-baseline.json"
    report_path = state / "l3" / f"{txid}.json"
    activated = False
    report = {
        "schema_version": 2,
        "transaction_id": txid,
        "mode": "L3_PROVISIONAL_DRY_RUN" if policy.dry_run else "L3_PROVISIONAL",
        "candidate_id": cid,
        "baseline_id": bid,
        "activated": False,
        "rolled_back": False,
        "status": "started",
        "events": [],
    }
    try:
        schema = validate_candidate(candidate, "strategy")
        if not schema["valid"]:
            raise RuntimeError("candidate_schema_violation")

        evidence = []
        for stage in ("development", "hidden_confirmation", "trigger_safety", "shadow"):
            item = runner(stage, baseline, candidate)
            if not isinstance(item, StageEvidence):
                raise TypeError("stage runner must return StageEvidence")
            evidence.append(item)
            report["events"].append(
                {
                    "stage": stage,
                    "passed": item.passed,
                    "safety_violations": item.safety_violations,
                    "artifact": item.artifact,
                    "real_execution": item.decision.get("real_execution") is True,
                }
            )
            if not item.passed or item.safety_violations:
                break

        gate_policy = FourStagePolicy(
            require_artifacts=policy.require_stage_artifacts,
            require_real_execution=policy.require_real_execution,
            autonomy_level="L3_PROVISIONAL",
        )
        decision = evaluate_four_stage(cid, bid, evidence, gate_policy)
        metrics = _metrics(evidence)
        report.update({"decision": decision, "metrics": metrics})
        if not decision["auto_promote"]:
            raise RuntimeError("four_stage_gate_rejected")
        if metrics["cost"] > policy.max_cost:
            raise RuntimeError("cost_budget_exceeded")
        if metrics["latency_s"] > policy.max_latency_s:
            raise RuntimeError("latency_budget_exceeded")
        if metrics["safety_violations"] > policy.max_safety_violations:
            raise RuntimeError("safety_budget_exceeded")

        decision_path = write_decision(root, decision)
        binding = None
        if policy.require_bundle_binding:
            if bundle is None:
                raise RuntimeError("candidate_bundle_required")
            binding = build_active_binding(candidate, bundle, txid, decision_path)
        if policy.require_valid_bundle:
            if bundle is None or bundle_verifier is None:
                raise RuntimeError("trusted_bundle_verifier_required")
            bundle_check = bundle_verifier(bundle["bundle_id"])
            report["bundle_verification"] = bundle_check
            if not bundle_check.get("valid"):
                raise RuntimeError("bundle_verification_failed")
        if binding is not None:
            report["active_binding"] = binding

        save_json(snapshot, baseline)
        if previous_binding is not None:
            save_json(state / "transactions" / f"{txid}-baseline-binding.json", previous_binding)
        if policy.dry_run:
            report["status"] = "dry_run_passed"
            report["would_activate"] = True
            report["would_write_binding"] = binding
        else:
            save_json(active_path, candidate)
            if binding is not None:
                save_json(binding_path, binding)
            activated = True
            report["activated"] = True
            report["events"].append(
                {"action": "active_switched", "candidate_id": cid, "bundle_id": binding.get("bundle_id") if binding else None}
            )
            health = (health_check or (lambda _: {"healthy": True}))(candidate)
            report["health_check"] = health
            if not health.get("healthy", False):
                raise RuntimeError("post_activation_health_failed")
            registry = VersionRegistry(state / "version-registry.json")
            if cid not in registry.data["versions"]:
                registry.register(
                    cid,
                    "agent_strategy",
                    "experimental",
                    {
                        "transaction_id": txid,
                        "bundle_id": binding.get("bundle_id") if binding else None,
                        "evidence_sha256": binding.get("evidence_sha256") if binding else None,
                    },
                )
            if registry.get(cid)["level"] == "experimental":
                registry.transition(
                    cid,
                    "provisional",
                    {
                        "development_passed": True,
                        "rollback_available": True,
                        "four_stage_passed": True,
                        "real_execution": True,
                        "transaction_id": txid,
                        "bundle_id": binding.get("bundle_id") if binding else None,
                        "evidence_sha256": binding.get("evidence_sha256") if binding else None,
                    },
                    reason="L3 provisional activation with verified artifacts and bundle binding",
                )
            report["status"] = "activated_provisional"
    except Exception as exc:
        report["status"] = "rejected" if not activated else "rolled_back"
        report["error"] = f"{type(exc).__name__}: {exc}"
        if activated and snapshot.exists():
            save_json(active_path, load_json(snapshot))
            if previous_binding is not None:
                save_json(binding_path, previous_binding)
            else:
                binding_path.unlink(missing_ok=True)
            report["rolled_back"] = True
            report["events"].append({"action": "automatic_rollback", "to": bid})
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_json(report_path, report)
        _unlock(lock_path, fd)
    return report
