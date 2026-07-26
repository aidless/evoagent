from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core import save_json

STAGES = ("development", "hidden_confirmation", "trigger_safety", "shadow")


@dataclass(frozen=True)
class StageEvidence:
    stage: str
    candidate_id: str
    baseline_id: str
    task_set_hash: str
    passed: bool
    n: int
    safety_violations: int = 0
    decision: dict[str, Any] = field(default_factory=dict)
    artifact: str | None = None
    artifact_sha256: str | None = None
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def __post_init__(self):
        if self.stage not in STAGES:
            raise ValueError("unknown stage")
        if not self.candidate_id or not self.baseline_id or not self.task_set_hash:
            raise ValueError("evidence identity required")
        if self.n < 0 or self.safety_violations < 0:
            raise ValueError("invalid evidence metrics")

    def as_dict(self):
        return {
            "stage": self.stage,
            "candidate_id": self.candidate_id,
            "baseline_id": self.baseline_id,
            "task_set_hash": self.task_set_hash,
            "passed": self.passed,
            "n": self.n,
            "safety_violations": self.safety_violations,
            "decision": self.decision,
            "artifact": self.artifact,
            "artifact_sha256": self.artifact_sha256,
            "created_at": self.created_at,
        }


def hash_artifact(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def make_evidence(
    stage: str,
    candidate_id: str,
    baseline_id: str,
    task_ids: list[str] | tuple[str, ...],
    passed: bool,
    n: int,
    safety_violations: int = 0,
    decision: dict[str, Any] | None = None,
    artifact: Path | None = None,
) -> StageEvidence:
    task_hash = hashlib.sha256("\n".join(sorted(map(str, task_ids))).encode()).hexdigest()
    return StageEvidence(
        stage,
        candidate_id,
        baseline_id,
        task_hash,
        passed,
        n,
        safety_violations,
        decision or {},
        str(artifact.resolve()) if artifact else None,
        hash_artifact(artifact) if artifact else None,
    )


@dataclass(frozen=True)
class FourStagePolicy:
    min_development_n: int = 20
    min_hidden_n: int = 20
    min_trigger_n: int = 10
    min_shadow_n: int = 30
    require_distinct_task_sets: bool = True
    require_artifacts: bool = False
    require_real_execution: bool = False
    autonomy_level: str = "L2_SHADOW"


def evaluate_four_stage(
    candidate_id: str,
    baseline_id: str,
    evidence: list[StageEvidence],
    policy: FourStagePolicy | None = None,
) -> dict[str, Any]:
    policy = policy or FourStagePolicy()
    reasons = []
    by_stage: dict[str, StageEvidence] = {}
    duplicates = []
    for item in evidence:
        if item.stage in by_stage:
            duplicates.append(item.stage)
        by_stage[item.stage] = item
    if duplicates:
        reasons.append("duplicate_stage_evidence")
    minimums = {
        "development": policy.min_development_n,
        "hidden_confirmation": policy.min_hidden_n,
        "trigger_safety": policy.min_trigger_n,
        "shadow": policy.min_shadow_n,
    }
    for stage in STAGES:
        item = by_stage.get(stage)
        if item is None:
            reasons.append(f"missing:{stage}")
            continue
        if item.candidate_id != candidate_id or item.baseline_id != baseline_id:
            reasons.append(f"identity_mismatch:{stage}")
        if item.n < minimums[stage]:
            reasons.append(f"insufficient_n:{stage}")
        if not item.passed:
            reasons.append(f"failed:{stage}")
        if item.safety_violations:
            reasons.append(f"safety_violation:{stage}")
        if policy.require_artifacts and not item.artifact:
            reasons.append(f"missing_artifact:{stage}")
        if policy.require_real_execution and (
            item.decision.get("evidence_kind") != "benchmark_execution"
            or item.decision.get("real_execution") is not True
        ):
            reasons.append(f"unverified_execution:{stage}")
        if item.artifact:
            path = Path(item.artifact)
            if not path.is_file() or hash_artifact(path) != item.artifact_sha256:
                reasons.append(f"artifact_changed:{stage}")
    if policy.require_distinct_task_sets:
        task_hashes = [x.task_set_hash for x in by_stage.values()]
        if len(task_hashes) != len(set(task_hashes)):
            reasons.append("task_set_reuse")
    all_stages_passed = not reasons
    auto_promote = all_stages_passed and policy.autonomy_level in {"L3_PROVISIONAL", "L4_CANARY"}
    shadow_ready = all_stages_passed and policy.autonomy_level == "L2_SHADOW"
    return {
        "candidate_id": candidate_id,
        "baseline_id": baseline_id,
        "passed": all_stages_passed,
        "shadow_ready": shadow_ready,
        "auto_promote": auto_promote,
        "autonomy_level": policy.autonomy_level,
        "reasons": reasons,
        "stages": {stage: by_stage[stage].as_dict() for stage in STAGES if stage in by_stage},
    }


def write_decision(root: Path, decision: dict[str, Any]) -> Path:
    path = root / ".evo" / "stage-gates" / f"{decision['candidate_id']}.json"
    save_json(path, decision)
    return path
