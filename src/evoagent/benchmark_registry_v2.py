from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 2
DOMAINS = ("math", "date", "logic", "research", "code", "tool", "memory", "safety")
STAGES = ("development", "hidden_confirmation", "trigger_safety", "shadow")
SAFETY_LEVELS = ("normal", "high")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def task_content_sha256(
    task_id: str,
    domain: str,
    stage: str,
    input_value: Any,
    success_criteria: dict[str, Any],
    source: str,
) -> str:
    """Hash public task content without including the sealed answer."""
    return sha256_json(
        {
            "task_id": task_id,
            "domain": domain,
            "stage": stage,
            "input": input_value,
            "success_criteria": success_criteria,
            "source": source,
        }
    )


@dataclass(frozen=True)
class BenchmarkTaskV2:
    task_id: str
    domain: str
    stage: str
    input: Any
    expected: Any
    success_criteria: dict[str, Any]
    allowed_tools: tuple[str, ...] = ()
    safety_level: str = "normal"
    source: str = ""
    license: str = "unknown"
    release_date: str = "unknown"
    snapshot_date: str = ""
    content_sha256: str = ""
    hidden: bool = False
    contamination_checked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if self.domain not in DOMAINS:
            raise ValueError(f"unknown domain: {self.domain}")
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage: {self.stage}")
        if self.safety_level not in SAFETY_LEVELS:
            raise ValueError(f"unknown safety level: {self.safety_level}")
        if not isinstance(self.success_criteria, dict) or not self.success_criteria:
            raise ValueError("success_criteria is required")
        if not self.source:
            raise ValueError("source is required")
        if not self.snapshot_date:
            raise ValueError("snapshot_date is required")
        expected_hash = task_content_sha256(
            self.task_id,
            self.domain,
            self.stage,
            self.input,
            self.success_criteria,
            self.source,
        )
        if self.content_sha256 and self.content_sha256 != expected_hash:
            raise ValueError(f"content hash mismatch: {self.task_id}")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", expected_hash)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BenchmarkTaskV2":
        data = dict(value)
        data["allowed_tools"] = tuple(data.get("allowed_tools", ()))
        return cls(**data)

    def as_dict(self, include_expected: bool = True) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_tools"] = list(self.allowed_tools)
        if not include_expected:
            data["expected"] = None
        return data


class BenchmarkRegistryV2:
    """Versioned task registry with a public manifest and a separately sealed answer key."""

    def __init__(
        self,
        tasks: Iterable[BenchmarkTaskV2],
        *,
        split_seed: int | None = None,
        manifest_sha256: str | None = None,
    ) -> None:
        self.tasks = tuple(tasks)
        self.split_seed = split_seed
        self.manifest_sha256 = manifest_sha256
        self._by_id = {task.task_id: task for task in self.tasks}
        if len(self._by_id) != len(self.tasks):
            raise ValueError("duplicate task_id")

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        answer_key_path: Path | None = None,
        *,
        expected_manifest_sha256: str | None = None,
        expected_answer_key_sha256: str | None = None,
    ) -> "BenchmarkRegistryV2":
        manifest_hash = sha256_file(manifest_path)
        if expected_manifest_sha256 and manifest_hash != expected_manifest_sha256:
            raise ValueError("manifest hash does not match the frozen registry")
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if payload.get("redacted"):
            raise PermissionError("benchmark registry is redacted in the candidate workspace")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported benchmark registry schema")
        tasks = [BenchmarkTaskV2.from_dict(row) for row in payload.get("tasks", [])]
        if answer_key_path is not None:
            answer_key_hash = sha256_file(answer_key_path)
            if expected_answer_key_sha256 and answer_key_hash != expected_answer_key_sha256:
                raise ValueError("answer key hash does not match the frozen registry")
            key = json.loads(answer_key_path.read_text(encoding="utf-8-sig"))
            if key.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("unsupported answer key schema")
            if key.get("manifest_sha256") != manifest_hash:
                raise ValueError("answer key is not bound to this manifest")
            answers = {row["task_id"]: row["expected"] for row in key.get("answers", [])}
            if set(answers) != {task.task_id for task in tasks}:
                raise ValueError("answer key task set mismatch")
            tasks = [replace(task, expected=answers[task.task_id]) for task in tasks]
        registry = cls(tasks, split_seed=payload.get("split_seed"), manifest_sha256=manifest_hash)
        registry.validate(require_answers=answer_key_path is not None)
        return registry

    def validate(self, require_answers: bool = False) -> dict[str, Any]:
        reasons: list[str] = []
        seen_content: dict[str, str] = {}
        for task in self.tasks:
            expected_hash = task_content_sha256(
                task.task_id,
                task.domain,
                task.stage,
                task.input,
                task.success_criteria,
                task.source,
            )
            if task.content_sha256 != expected_hash:
                reasons.append(f"content_hash_mismatch:{task.task_id}")
            if require_answers and task.expected is None:
                reasons.append(f"missing_answer:{task.task_id}")
            semantic_hash = sha256_json(
                {
                    "domain": task.domain,
                    "input": task.input,
                    "success_criteria": task.success_criteria,
                    "source": task.source,
                }
            )
            prior = seen_content.get(semantic_hash)
            if prior:
                reasons.append(f"duplicate_content:{prior}:{task.task_id}")
            seen_content[semantic_hash] = task.task_id
        return {
            "valid": not reasons,
            "reasons": reasons,
            "summary": self.summary(),
        }

    def select(self, *, stage: str | None = None, domain: str | None = None) -> tuple[BenchmarkTaskV2, ...]:
        if stage is not None and stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        if domain is not None and domain not in DOMAINS:
            raise ValueError(f"unknown domain: {domain}")
        return tuple(
            task
            for task in self.tasks
            if (stage is None or task.stage == stage) and (domain is None or task.domain == domain)
        )

    def task_set_hash(self, tasks: Iterable[BenchmarkTaskV2] | None = None) -> str:
        selected = tuple(tasks) if tasks is not None else self.tasks
        return hashlib.sha256(
            "\n".join(sorted(f"{task.task_id}:{task.content_sha256}" for task in selected)).encode("utf-8")
        ).hexdigest()

    def summary(self) -> dict[str, Any]:
        by_stage = {stage: 0 for stage in STAGES}
        by_domain = {domain: 0 for domain in DOMAINS}
        hidden = contamination_checked = answered = 0
        for task in self.tasks:
            by_stage[task.stage] += 1
            by_domain[task.domain] += 1
            hidden += int(task.hidden)
            contamination_checked += int(task.contamination_checked)
            answered += int(task.expected is not None)
        return {
            "schema_version": SCHEMA_VERSION,
            "tasks": len(self.tasks),
            "by_stage": by_stage,
            "by_domain": by_domain,
            "hidden": hidden,
            "answers_loaded": answered,
            "contamination_checked": contamination_checked,
            "task_set_sha256": self.task_set_hash(),
            "split_seed": self.split_seed,
        }

    def get(self, task_id: str) -> BenchmarkTaskV2:
        return self._by_id[task_id]


def write_registry(
    tasks: Iterable[BenchmarkTaskV2],
    manifest_path: Path,
    answer_key_path: Path,
    *,
    split_seed: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = BenchmarkRegistryV2(tasks, split_seed=split_seed)
    validation = registry.validate(require_answers=True)
    if not validation["valid"]:
        raise ValueError("invalid registry: " + ",".join(validation["reasons"]))

    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "split_seed": split_seed,
        "metadata": metadata or {},
        "tasks": [task.as_dict(include_expected=False) for task in registry.tasks],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    answer_key_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    key_tmp = answer_key_path.with_suffix(answer_key_path.suffix + ".tmp")
    manifest_tmp.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(manifest_tmp, manifest_path)
    manifest_hash = sha256_file(manifest_path)
    key_payload = {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": manifest_hash,
        "answers": [
            {"task_id": task.task_id, "expected": task.expected}
            for task in registry.tasks
        ],
    }
    key_tmp.write_text(json.dumps(key_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(key_tmp, answer_key_path)
    loaded = BenchmarkRegistryV2.load(manifest_path, answer_key_path)
    return {
        "manifest": str(manifest_path),
        "answer_key": str(answer_key_path),
        "manifest_sha256": manifest_hash,
        "answer_key_sha256": sha256_file(answer_key_path),
        "summary": loaded.summary(),
    }
