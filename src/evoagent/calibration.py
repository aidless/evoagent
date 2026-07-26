from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SelectiveRecord:
    task_id: str
    answerable: bool
    abstained: bool
    correct: bool

    def __post_init__(self) -> None:
        if self.abstained and self.correct:
            raise ValueError("an abstention cannot also be a correct answer")


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def selective_metrics(records: Iterable[SelectiveRecord]) -> dict:
    rows = tuple(records)
    answered = [row for row in rows if not row.abstained]
    answerable = [row for row in rows if row.answerable]
    unanswerable = [row for row in rows if not row.answerable]
    correct_answered = sum(row.correct for row in answered)
    appropriate_abstentions = sum(row.abstained for row in unanswerable)
    unnecessary_abstentions = sum(row.abstained for row in answerable)
    return {
        "n": len(rows),
        "answerable_n": len(answerable),
        "unanswerable_n": len(unanswerable),
        "answered_n": len(answered),
        "coverage": _rate(len(answered), len(rows)),
        "selective_accuracy": _rate(correct_answered, len(answered)),
        "appropriate_abstention_rate": _rate(appropriate_abstentions, len(unanswerable)),
        "unnecessary_abstention_rate": _rate(unnecessary_abstentions, len(answerable)),
    }


def evaluate_calibration_gate(
    baseline: dict,
    candidate: dict,
    *,
    max_coverage_drop: float = 0.05,
    max_unnecessary_abstention_increase: float = 0.02,
    require_selective_accuracy_non_decrease: bool = True,
) -> dict:
    reasons: list[str] = []
    required = (
        "coverage",
        "selective_accuracy",
        "appropriate_abstention_rate",
        "unnecessary_abstention_rate",
    )
    for metric in required:
        if baseline.get(metric) is None or candidate.get(metric) is None:
            reasons.append(f"metric_unavailable:{metric}")
    if reasons:
        return {"passed": False, "reasons": reasons, "deltas": {}}

    deltas = {metric: candidate[metric] - baseline[metric] for metric in required}
    if deltas["coverage"] < -max_coverage_drop:
        reasons.append("coverage_regression")
    if deltas["unnecessary_abstention_rate"] > max_unnecessary_abstention_increase:
        reasons.append("unnecessary_abstention_regression")
    if require_selective_accuracy_non_decrease and deltas["selective_accuracy"] < 0:
        reasons.append("selective_accuracy_regression")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "deltas": deltas,
        "thresholds": {
            "max_coverage_drop": max_coverage_drop,
            "max_unnecessary_abstention_increase": max_unnecessary_abstention_increase,
            "require_selective_accuracy_non_decrease": require_selective_accuracy_non_decrease,
        },
    }
