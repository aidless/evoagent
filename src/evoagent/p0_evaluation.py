from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from .benchmark_registry_v2 import BenchmarkRegistryV2, BenchmarkTaskV2, STAGES
from .bundle_signer import verify_manifest_files
from .core import candidate_id, load_json, save_json
from .promotion_gate import evaluate_promotion
from .protocol import Outcome, Run
from .reasoning_tools import solve_date, solve_logic
from .signing import verify_envelope
from .version_registry import VersionRegistry

SUPPORTED_DOMAINS = ("date", "logic", "tool")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_choice(value: Any) -> str:
    match = re.search(r"\(?([A-Z])\)?", str(value).upper())
    return f"({match.group(1)})" if match else str(value).strip()


def _execute(task: BenchmarkTaskV2, strategy: dict[str, Any]) -> tuple[Any, str]:
    if task.domain == "date":
        answer = solve_date(str(task.input))
        return (_normalize_choice(answer) if answer else None), "deterministic_datetime_solver_v2"
    if task.domain == "logic":
        answer = solve_logic(str(task.input))
        return (_normalize_choice(answer) if answer else None), "permutation_constraint_solver_v3"
    if task.domain == "tool":
        value = task.input
        if not isinstance(value, str):
            return None, "text_normalizer_type_error"
        if strategy.get("trim_whitespace"):
            value = value.strip()
        if strategy.get("normalize_case"):
            value = value.lower()
        return value, "text_normalizer_strategy"
    raise ValueError(f"unsupported deterministic domain: {task.domain}")


def evaluate_strategy(
    registry: BenchmarkRegistryV2,
    strategy: dict[str, Any],
    *,
    stage: str | None = None,
) -> Run:
    tasks = tuple(
        task
        for task in registry.tasks
        if task.domain in SUPPORTED_DOMAINS and (stage is None or task.stage == stage)
    )
    outcomes = []
    for task in tasks:
        started = time.monotonic()
        try:
            output, executor = _execute(task, strategy)
            passed = output == task.expected
            error = None
        except Exception as exc:
            output = None
            executor = "failed_closed"
            passed = False
            error = f"{type(exc).__name__}: {exc}"
        outcomes.append(
            Outcome(
                task.task_id,
                passed,
                1.0 if passed else 0.0,
                cost=0.0,
                latency_s=time.monotonic() - started,
                safety_violations=0,
                capabilities={task.domain: 1.0 if passed else 0.0},
                details={
                    "stage": task.stage,
                    "domain": task.domain,
                    "executor": executor,
                    "output": output,
                    "error": error,
                    "real_execution": True,
                },
            )
        )
    return Run(
        run_id=f"p0-{stage or 'all'}-{candidate_id(strategy)}",
        candidate_id=candidate_id(strategy),
        task_set_hash=registry.task_set_hash(tasks),
        outcomes=tuple(outcomes),
        model={"kind": "deterministic_local", "temperature": 0},
        config={"supported_domains": list(SUPPORTED_DOMAINS), "stage": stage},
    )


def _score(run: Run) -> dict[str, Any]:
    outcomes = run.outcomes
    by_domain: dict[str, dict[str, Any]] = {}
    for domain in SUPPORTED_DOMAINS:
        rows = [row for row in outcomes if row.details.get("domain") == domain]
        if rows:
            by_domain[domain] = {
                "n": len(rows),
                "passed": sum(row.passed for row in rows),
                "score": sum(row.score for row in rows) / len(rows),
            }
    return {
        "run_id": run.run_id,
        "candidate_id": run.candidate_id,
        "task_set_hash": run.task_set_hash,
        "n": len(outcomes),
        "passed": sum(row.passed for row in outcomes),
        "score": sum(row.score for row in outcomes) / len(outcomes) if outcomes else 0.0,
        "by_domain": by_domain,
        "latency_s": sum(row.latency_s for row in outcomes),
        "safety_violations": sum(row.safety_violations for row in outcomes),
    }


def _audit_existing_l3(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    bundle_path = root / ".evo" / "v24-l3-bundle.json"
    activation_path = root / ".evo" / "l3" / "evolution-activation.json"
    result = {
        "bundle_path": str(bundle_path),
        "activation_path": str(activation_path),
        "bundle_candidate_bound": False,
        "stage_artifacts_present": False,
        "transaction_validated": False,
    }
    if bundle_path.is_file():
        bundle = load_json(bundle_path)
        result["bundle_id"] = bundle.get("bundle_id")
        result["bundle_sha256"] = bundle.get("sha256")
        result["bundle_candidate_bound"] = (
            bundle.get("manifest", {}).get("metadata", {}).get("candidate_id") == candidate_id(candidate)
        )
        result["bundle_manifest_integrity"] = verify_manifest_files(bundle)
        envelope_path = root / ".evo" / "v24-l3-envelope.json"
        if envelope_path.is_file():
            envelope = load_json(envelope_path)
            signer = envelope.get("signer")
            public_key = root / ".evo" / "trusted-keys" / f"{signer}.pub"
            result["bundle_signature"] = (
                verify_envelope(envelope, bundle, {signer: public_key.read_bytes()})
                if signer and public_key.is_file()
                else {"valid": False, "reason": "trusted_key_missing"}
            )
        else:
            result["bundle_signature"] = {"valid": False, "reason": "envelope_missing"}
    if activation_path.is_file():
        activation = load_json(activation_path)
        stages = activation.get("decision", {}).get("stages", {})
        result["transaction_validated"] = activation.get("status") == "activated_provisional"
        result["stage_artifacts_present"] = bool(stages) and all(
            row.get("artifact") and row.get("artifact_sha256") for row in stages.values()
        )
        result["activation_candidate_id"] = activation.get("candidate_id")
        result["transaction_id"] = activation.get("transaction_id")
    result["binding_valid"] = (
        result["bundle_candidate_bound"]
        and result["stage_artifacts_present"]
        and result.get("bundle_manifest_integrity", {}).get("valid", False)
        and result.get("bundle_signature", {}).get("valid", False)
    )
    return result


def reassess(
    root: Path,
    manifest_path: Path,
    answer_key_path: Path,
    baseline_path: Path,
    candidate_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    public_summary_path = root / "benchmarks" / "registry-v2" / "summary.json"
    frozen = load_json(public_summary_path) if public_summary_path.is_file() else {}
    registry = BenchmarkRegistryV2.load(
        manifest_path,
        answer_key_path,
        expected_manifest_sha256=frozen.get("manifest_sha256"),
        expected_answer_key_sha256=frozen.get("answer_key_sha256"),
    )
    baseline = load_json(baseline_path)
    candidate = load_json(candidate_path)
    stage_reports = {}
    all_promote = True
    for stage in STAGES:
        base_run = evaluate_strategy(registry, baseline, stage=stage)
        candidate_run = evaluate_strategy(registry, candidate, stage=stage)
        gate = evaluate_promotion(
            base_run,
            candidate_run,
            min_gain=0.01,
            alpha=0.05,
            max_capability_drop=0.01,
            bootstrap_iterations=1000,
        )
        all_promote = all_promote and gate.get("promote", False)
        stage_reports[stage] = {
            "baseline": _score(base_run),
            "candidate": _score(candidate_run),
            "promotion_gate": gate,
            "artifact_kind": "real_deterministic_execution",
        }
    base_all = evaluate_strategy(registry, baseline)
    candidate_all = evaluate_strategy(registry, candidate)
    overall_gate = evaluate_promotion(
        base_all,
        candidate_all,
        min_gain=0.01,
        alpha=0.05,
        max_capability_drop=0.01,
        bootstrap_iterations=2000,
    )
    registry_summary = registry.summary()
    evaluated_domains = list(SUPPORTED_DOMAINS)
    unevaluated_domains = [domain for domain in registry_summary["by_domain"] if domain not in SUPPORTED_DOMAINS]
    full_registry_evaluated = not unevaluated_domains
    calibration_evaluated = "safety" in evaluated_domains
    binding = _audit_existing_l3(root, candidate)
    benchmark_confirmed = (
        full_registry_evaluated
        and calibration_evaluated
        and binding["binding_valid"]
        and all_promote
        and overall_gate.get("promote", False)
    )
    reasons = []
    if not overall_gate.get("promote", False):
        reasons.append("no_verified_candidate_gain")
    if not full_registry_evaluated:
        reasons.append("incomplete_domain_coverage")
    if not calibration_evaluated:
        reasons.append("calibration_and_abstention_not_evaluated")
    if not binding.get("bundle_manifest_integrity", {}).get("valid", False):
        reasons.append("active_bundle_manifest_invalid")
    if not binding["binding_valid"]:
        reasons.append("candidate_bundle_evidence_binding_missing")
    report = {
        "schema_version": 1,
        "evaluation_kind": "p0_real_deterministic_reassessment",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "registry": {
            "manifest": str(manifest_path.resolve()),
            "manifest_sha256": _sha256_file(manifest_path),
            "answer_key_sha256": _sha256_file(answer_key_path),
            "summary": registry_summary,
        },
        "baseline_id": candidate_id(baseline),
        "candidate_id": candidate_id(candidate),
        "evaluated_domains": evaluated_domains,
        "unevaluated_domains": unevaluated_domains,
        "real_execution": True,
        "deterministic": True,
        "full_registry_evaluated": full_registry_evaluated,
        "calibration_evaluated": calibration_evaluated,
        "stage_reports": stage_reports,
        "overall": {
            "baseline": _score(base_all),
            "candidate": _score(candidate_all),
            "promotion_gate": overall_gate,
        },
        "existing_l3_audit": binding,
        "benchmark_confirmed": benchmark_confirmed,
        "candidate_status": "benchmark-confirmed" if benchmark_confirmed else "transaction-validated_benchmark-unconfirmed",
        "stable_promotion_allowed": benchmark_confirmed,
        "recommendation": "eligible_for_next_gate" if benchmark_confirmed else "keep_provisional_and_block_stable_promotion",
        "reasons": reasons,
        "limitations": [
            "The deterministic pass covers date, logic, and text-normalization tasks only.",
            "Math, research, code, memory, and safety require controlled model/sandbox runners.",
            "No stochastic model was used, so multi-seed mean and standard deviation are not applicable to this pass.",
        ],
    }
    output_path = output_path or root / ".evo" / "benchmark-registry-v2" / f"reassessment-{report['candidate_id']}.json"
    save_json(output_path, report)
    status = {
        "candidate_id": report["candidate_id"],
        "candidate_status": report["candidate_status"],
        "stable_promotion_allowed": report["stable_promotion_allowed"],
        "report": str(output_path.resolve()),
        "report_sha256": _sha256_file(output_path),
        "reasons": reasons,
    }
    save_json(output_path.parent / "current-status.json", status)
    version_registry = VersionRegistry(root / ".evo" / "version-registry.json")
    if report["candidate_id"] in version_registry.data.get("versions", {}):
        evidence = {
            "transaction_validated": binding.get("transaction_validated", False),
            "benchmark_confirmed": benchmark_confirmed,
            "stable_promotion_allowed": benchmark_confirmed,
            "evidence_status": report["candidate_status"],
            "benchmark_report_sha256": status["report_sha256"],
        }
        current = version_registry.get(report["candidate_id"]).get("evidence", {})
        if any(current.get(key) != value for key, value in evidence.items()):
            version_registry.annotate(
                report["candidate_id"],
                evidence,
                reason="P0 real benchmark reassessment",
            )
    return {"report": report, "artifact": str(output_path), "artifact_sha256": status["report_sha256"]}


def _default_private_registry(root: Path) -> tuple[Path, Path]:
    private_root = root.parent / f"{root.name}-private" / "benchmark-registry-v2"
    return private_root / "tasks.json", private_root / "answer-key.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reassess the active L3 candidate with real local tasks")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--answer-key", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    default_manifest, default_key = _default_private_registry(root)
    baseline = args.baseline or root / ".evo" / "transactions" / "l3-20260724-213644-3e45cc7e-baseline.json"
    candidate = args.candidate or root / ".evo" / "active.json"
    result = reassess(
        root,
        (args.manifest or default_manifest).resolve(),
        (args.answer_key or default_key).resolve(),
        baseline.resolve(),
        candidate.resolve(),
        args.output.resolve() if args.output else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
