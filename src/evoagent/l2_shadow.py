from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .core import candidate_id, load_json, save_json
from .stage_gates import FourStagePolicy, StageEvidence, evaluate_four_stage, write_decision

StageRunner = Callable[[str, dict, dict], StageEvidence]


@dataclass(frozen=True)
class L2RunResult:
    report: dict
    path: Path


def run_l2_shadow(root: Path, candidate: dict, runner: StageRunner) -> L2RunResult:
    """Evaluate a candidate through all four gates without activating it."""
    root = root.resolve()
    baseline = load_json(root / ".evo" / "active.json")
    candidate_value = candidate_id(candidate)
    baseline_value = candidate_id(baseline)
    evidence = []
    for stage in ("development", "hidden_confirmation", "trigger_safety", "shadow"):
        item = runner(stage, baseline, candidate)
        if not isinstance(item, StageEvidence):
            raise TypeError("stage runner must return StageEvidence")
        evidence.append(item)
        if not item.passed or item.safety_violations:
            break
    decision = evaluate_four_stage(
        candidate_value,
        baseline_value,
        evidence,
        FourStagePolicy(autonomy_level="L2_SHADOW"),
    )
    report = {
        "schema_version": 1,
        "mode": "L2_SHADOW",
        "candidate_id": candidate_value,
        "baseline_id": baseline_value,
        "active_changed": False,
        "decision": decision,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = root / ".evo" / "l2-shadow" / f"{candidate_value}.json"
    save_json(path, report)
    write_decision(root, decision)
    return L2RunResult(report, path)
