from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import EvalResult, candidate_id, canonical, load_json, save_json


@dataclass(frozen=True)
class FailureDiagnosis:
    total: int
    failed: int
    failure_rate: float
    task_ids: tuple[str, ...]
    categories: dict[str, int]
    capability_gaps: dict[str, float]
    error_types: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "failed": self.failed,
            "failure_rate": self.failure_rate,
            "task_ids": list(self.task_ids),
            "categories": self.categories,
            "capability_gaps": self.capability_gaps,
            "error_types": self.error_types,
        }


def _category(row: dict[str, Any]) -> str:
    details = row.get("details") or {}
    explicit = details.get("category") or details.get("suite") or details.get("domain")
    if explicit:
        return str(explicit)
    task_id = str(row.get("task_id", "unknown"))
    for separator in (":", "/", "-"):
        if separator in task_id:
            return task_id.split(separator, 1)[0]
    return "general"


def diagnose(result: EvalResult) -> FailureDiagnosis:
    failed_rows = [row for row in result.outcomes if not row.get("passed", False)]
    categories = Counter(_category(row) for row in failed_rows)
    errors = Counter()
    capability_totals: dict[str, list[float]] = defaultdict(list)
    for row in failed_rows:
        details = row.get("details") or {}
        if details.get("error"):
            error = str(details["error"]).split(":", 1)[0]
            errors[error] += 1
        for name, value in (row.get("capabilities") or {}).items():
            try:
                capability_totals[str(name)].append(float(value))
            except (TypeError, ValueError):
                continue
    gaps = {
        name: round(1.0 - sum(values) / len(values), 6)
        for name, values in capability_totals.items()
        if values
    }
    return FailureDiagnosis(
        result.total,
        len(failed_rows),
        len(failed_rows) / result.total if result.total else 0.0,
        tuple(str(row.get("task_id", "unknown")) for row in failed_rows),
        dict(categories),
        gaps,
        dict(errors),
    )


class ExperienceStore:
    """Append-only learning memory derived only from observed evaluations."""

    def __init__(self, path: Path):
        self.path = path
        self.data = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.exists()
            else {"schema_version": 1, "experiences": [], "mutation_stats": {}}
        )

    def _save(self) -> None:
        save_json(self.path, self.data)

    def record(
        self,
        run_id: str,
        parent: dict[str, Any],
        candidate: dict[str, Any],
        baseline: EvalResult,
        result: EvalResult,
        decision: dict[str, Any],
        promoted: bool = False,
    ) -> dict[str, Any]:
        parent_id = candidate_id(parent)
        cid = candidate_id(candidate)
        patch = diff(parent, candidate)
        row = {
            "experience_id": f"{run_id}:{cid}",
            "run_id": run_id,
            "parent_id": parent_id,
            "candidate_id": cid,
            "patch": patch,
            "baseline_score": baseline.score,
            "candidate_score": result.score,
            "gain": result.score - baseline.score,
            "diagnosis": diagnose(result).as_dict(),
            "decision": decision,
            "promoted": promoted,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        existing = {x["experience_id"] for x in self.data["experiences"]}
        if row["experience_id"] not in existing:
            self.data["experiences"].append(row)
            signature = canonical(patch)
            stats = self.data["mutation_stats"].setdefault(
                signature,
                {"patch": patch, "trials": 0, "wins": 0, "promotions": 0, "total_gain": 0.0},
            )
            stats["trials"] += 1
            stats["wins"] += int(row["gain"] > 0)
            stats["promotions"] += int(promoted)
            stats["total_gain"] += row["gain"]
            stats["mean_gain"] = stats["total_gain"] / stats["trials"]
            self._save()
        return row

    def mark_promoted(self, run_id: str, candidate_id_value: str) -> None:
        changed = False
        for row in self.data["experiences"]:
            if row["run_id"] == run_id and row["candidate_id"] == candidate_id_value:
                if not row.get("promoted"):
                    row["promoted"] = True
                    signature = canonical(row["patch"])
                    self.data["mutation_stats"][signature]["promotions"] += 1
                    changed = True
        if changed:
            self._save()

    def successful_patches(self, limit: int = 5, min_trials: int = 1) -> list[dict[str, Any]]:
        rows = [
            value
            for value in self.data["mutation_stats"].values()
            if value["trials"] >= min_trials and value.get("mean_gain", 0.0) > 0
        ]
        rows.sort(
            key=lambda row: (
                row.get("promotions", 0),
                row.get("mean_gain", 0.0),
                row.get("wins", 0) / row["trials"],
            ),
            reverse=True,
        )
        return [deepcopy(row["patch"]) for row in rows[:limit]]

    def summary(self) -> dict[str, Any]:
        experiences = self.data["experiences"]
        return {
            "experiences": len(experiences),
            "mutations": len(self.data["mutation_stats"]),
            "positive": sum(x.get("gain", 0) > 0 for x in experiences),
            "promoted": sum(bool(x.get("promoted")) for x in experiences),
        }


def diff(parent: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    patch = {}
    for key, value in candidate.items():
        if key not in parent or parent[key] != value:
            patch[key] = deepcopy(value)
    return patch


def apply_patch(candidate: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(candidate)
    result.update(deepcopy(patch))
    return result


class AdaptiveProposer:
    """Combine configured, external, and experience-derived proposals."""

    def __init__(self, store: ExperienceStore, base_proposer=None):
        self.store = store
        self.base_proposer = base_proposer

    def __call__(
        self, root: Path, incumbent: dict[str, Any], failures: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        config = load_json(root / "evo.json")
        raw = config.get("adaptive_proposer", {})
        proposals: list[dict[str, Any]] = []
        if self.base_proposer is not None:
            proposals.extend(self.base_proposer(root, incumbent, failures))
        for patch in self.store.successful_patches(
            limit=max(0, int(raw.get("memory_candidates", 5))),
            min_trials=max(1, int(raw.get("min_trials", 1))),
        ):
            proposals.append(apply_patch(incumbent, patch))
        for category in sorted({_failure_family(value) for value in failures}):
            patch = (raw.get("failure_mutations", {}) or {}).get(category)
            if isinstance(patch, dict):
                proposals.append(apply_patch(incumbent, patch))
        unique = []
        seen = set()
        for candidate in proposals:
            cid = candidate_id(candidate)
            if cid not in seen:
                seen.add(cid)
                unique.append(candidate)
        return unique


def _failure_family(task_id: str) -> str:
    text = str(task_id)
    for separator in (":", "/", "-"):
        if separator in text:
            return text.split(separator, 1)[0]
    return text
