from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from .benchmark_registry_v2 import sha256_file
from .core import candidate_id, load_json, save_json
from .version_registry import VersionRegistry


def assess_rollback(deterministic_report: dict[str, Any], safety_report: dict[str, Any]) -> dict[str, Any]:
    overall = deterministic_report.get("overall", {}).get("promotion_gate", {})
    baseline = safety_report.get("baseline", {})
    candidate = safety_report.get("candidate", {})
    no_verified_gain = float(overall.get("mean_gain", 0.0)) <= 0 or not overall.get("promote", False)
    safety_trigger_failed = int(candidate.get("safety_violations", 0)) > 0
    safety_regression = (
        int(candidate.get("safety_violations", 0)) > int(baseline.get("safety_violations", 0))
        or float(candidate.get("harmful_refusal_rate", 0.0)) < float(baseline.get("harmful_refusal_rate", 0.0))
    )
    calibration_failed = not safety_report.get("calibration_gate", {}).get("passed", False)
    reasons = []
    if no_verified_gain:
        reasons.append("no_verified_candidate_gain")
    if safety_trigger_failed:
        reasons.append("candidate_safety_trigger_failed")
    if safety_regression:
        reasons.append("candidate_safety_regression")
    if calibration_failed:
        reasons.append("candidate_calibration_gate_failed")
    return {
        "rollback_required": safety_trigger_failed or safety_regression or calibration_failed,
        "reasons": reasons,
        "no_verified_gain": no_verified_gain,
        "safety_trigger_failed": safety_trigger_failed,
        "safety_regression": safety_regression,
        "calibration_failed": calibration_failed,
        "baseline_safety_violations": baseline.get("safety_violations"),
        "candidate_safety_violations": candidate.get("safety_violations"),
        "baseline_harmful_refusal_rate": baseline.get("harmful_refusal_rate"),
        "candidate_harmful_refusal_rate": candidate.get("harmful_refusal_rate"),
    }


def _acquire_lock(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("l3_run_already_active") from exc
    os.write(fd, json.dumps({"pid": os.getpid(), "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}).encode())
    return fd


def _release_lock(path: Path, fd: int) -> None:
    os.close(fd)
    path.unlink(missing_ok=True)


def rollback_from_evidence(
    root: Path,
    deterministic_report_path: Path,
    safety_report_path: Path,
    baseline_path: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    state = root / ".evo"
    status_path = state / "benchmark-registry-v2" / "current-status.json"
    status = load_json(status_path)
    if status.get("report_sha256") != sha256_file(deterministic_report_path):
        raise RuntimeError("deterministic report hash mismatch")
    if status.get("safety_calibration_sha256") != sha256_file(safety_report_path):
        raise RuntimeError("safety report hash mismatch")
    deterministic = load_json(deterministic_report_path)
    safety = load_json(safety_report_path)
    active_path = state / "active.json"
    active = load_json(active_path)
    baseline = load_json(baseline_path)
    active_id = candidate_id(active)
    baseline_id = candidate_id(baseline)
    expected_candidate = deterministic.get("candidate_id")
    if active_id != expected_candidate or safety.get("candidate", {}).get("candidate_id") != expected_candidate:
        raise RuntimeError("active candidate does not match evaluated candidate")
    if deterministic.get("baseline_id") != baseline_id or safety.get("baseline", {}).get("candidate_id") != baseline_id:
        raise RuntimeError("rollback baseline does not match evaluated baseline")

    assessment = assess_rollback(deterministic, safety)
    txid = f"p0-rollback-{time.strftime('%Y%m%d-%H%M%S')}"
    report = {
        "schema_version": 1,
        "transaction_id": txid,
        "mode": "APPLY" if apply else "DRY_RUN",
        "from_candidate_id": active_id,
        "to_candidate_id": baseline_id,
        "assessment": assessment,
        "applied": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "evidence": {
            "deterministic_report": str(deterministic_report_path.resolve()),
            "deterministic_report_sha256": sha256_file(deterministic_report_path),
            "safety_report": str(safety_report_path.resolve()),
            "safety_report_sha256": sha256_file(safety_report_path),
        },
    }
    if apply and assessment["rollback_required"]:
        lock_path = state / "locks" / "l3.lock"
        fd = _acquire_lock(lock_path)
        try:
            history_path = state / "history" / f"{time.strftime('%Y%m%d-%H%M%S')}-pre-p0-safety-rollback.json"
            save_json(history_path, active)
            save_json(state / "transactions" / f"{txid}-from.json", active)
            save_json(state / "transactions" / f"{txid}-to.json", baseline)
            binding_path = state / "active-binding.json"
            if binding_path.exists():
                save_json(state / "transactions" / f"{txid}-binding.json", load_json(binding_path))
                binding_path.unlink()
            save_json(active_path, baseline)
            registry = VersionRegistry(state / "version-registry.json")
            if active_id in registry.data.get("versions", {}) and registry.get(active_id)["level"] != "experimental":
                registry.transition(
                    active_id,
                    "experimental",
                    {
                        "safety_calibration_passed": False,
                        "stable_promotion_allowed": False,
                        "rollback_transaction_id": txid,
                    },
                    reason="automatic rollback after real safety/calibration failure",
                )
            if baseline_id not in registry.data.get("versions", {}):
                registry.register(
                    baseline_id,
                    "agent_strategy",
                    "experimental",
                    {
                        "rollback_target": True,
                        "activated_due_to_safety_rollback": True,
                        "benchmark_confirmed": False,
                        "stable_promotion_allowed": False,
                        "rollback_transaction_id": txid,
                    },
                )
            status.update(
                {
                    "candidate_id": baseline_id,
                    "candidate_status": "experimental_safety_fallback",
                    "stable_promotion_allowed": False,
                    "rolled_back": True,
                    "rollback_from": active_id,
                    "rollback_to": baseline_id,
                    "rollback_transaction_id": txid,
                    "rollback_reasons": assessment["reasons"],
                    "active_bundle_valid": False,
                }
            )
            save_json(status_path, status)
            save_json(
                state / "rollback-last.json",
                {
                    "from": active_id,
                    "to": baseline_id,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "transaction_id": txid,
                    "reason": "real safety/calibration failure",
                },
            )
            report["applied"] = True
            report["history_snapshot"] = str(history_path)
        finally:
            _release_lock(lock_path, fd)
    elif apply:
        report["status"] = "not_required"
    else:
        report["status"] = "would_rollback" if assessment["rollback_required"] else "not_required"
    report_path = state / "benchmark-registry-v2" / f"{txid}.json"
    save_json(report_path, report)
    report["artifact"] = str(report_path)
    report["artifact_sha256"] = sha256_file(report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely roll back an L3 candidate after verified P0 failure")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--deterministic-report", type=Path)
    parser.add_argument("--safety-report", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    status = load_json(root / ".evo" / "benchmark-registry-v2" / "current-status.json")
    result = rollback_from_evidence(
        root,
        (args.deterministic_report or Path(status["report"])).resolve(),
        (args.safety_report or Path(status["safety_calibration_report"])).resolve(),
        (args.baseline or root / ".evo" / "transactions" / "l3-20260724-213644-3e45cc7e-baseline.json").resolve(),
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
