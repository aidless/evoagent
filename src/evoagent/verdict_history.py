"""per-edit 判定的落盘历史（JSONL）与按 kind 的聚合。

change_manifest 的对账结果只在单次 evolve 报告里，跨 run 就散失；本模块把
每次 evolve 的 per-edit 判定追加成一行一候选的 JSONL（`.evo/verdicts.jsonl`），
成为下游共享的同一份证据：P4 的信任度打分器读它算「哪类改动值得信」，
P3 的技能编译器读它挑应该写成教训的失败。

为什么单独一个文件而不是从 runs/*.json 反查：runs 报告会随保留策略被清，
verdicts.jsonl 是 append-only 的信任账本，删它等于丢掉历史精度。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

HISTORY_NAME = "verdicts.jsonl"


def _history_path(state_dir: Path) -> Path:
    return Path(state_dir) / HISTORY_NAME


def append_verdicts(state_dir: Path, run_id: str,
                    records: Iterable[dict[str, Any]]) -> int:
    """把一批候选记录里的 change_verdict 追加成历史行，返回写入条数。

    只写带 change_verdict 的候选（None 表示该候选没声明预测，不构成证据）。
    畸形 manifest 的 fail-closed 判定也写（valid=False），否则被拦的次数看不见。
    """
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(_history_path(state_dir), "a", encoding="utf-8") as fh:
        for record in records:
            verdict = record.get("change_verdict")
            if verdict is None:
                continue
            edits = []
            for edit_id, edit in (verdict.get("edits") or {}).items():
                edits.append({
                    "edit_id": edit.get("edit_id", edit_id),
                    "kind": edit.get("kind", ""),
                    "files": list(edit.get("files") or ()),
                    "verdict": edit.get("verdict", "invalid_prediction"),
                    "hits": list(edit.get("hits") or ()),
                    "prediction_precision": edit.get("prediction_precision"),
                    "predicted_fix": list(edit.get("predicted_fix") or ()),
                    "predicted_regression": list(edit.get("predicted_regression") or ()),
                })
            campaign = verdict.get("campaign") or {}
            row = {
                "run_id": run_id,
                "candidate_id": record.get("id", ""),
                "valid": bool(verdict.get("valid", True)),
                "reasons": list(verdict.get("reasons") or ()),
                "prediction_precision": campaign.get("prediction_precision"),
                "predicted_total": campaign.get(
                    "predicted_total", campaign.get("total_predicted", 0)),
                "hit_total": campaign.get("hit_total", campaign.get("total_hit", 0)),
                "edits": edits,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def read_verdicts(root: Path) -> list[dict[str, Any]]:
    """读回历史行；坏行跳过（历史是 append-only，不因一行损坏整份不可用）。"""
    path = _history_path(Path(root) / ".evo")
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """按 edit kind 聚合：编辑数、判定分布、平均预测精度，以及总体精度。

    平均精度只对有效（valid=True）且带精度的 edit 计，避免 fail-closed 的
    0/None 拉低「声明质量」这个指标——被拦是治理成功，不是预测不准。
    """
    kinds: dict[str, dict[str, Any]] = {}
    campaign_precisions: list[float] = []
    campaigns = 0
    invalid = 0
    for row in rows:
        campaigns += 1
        if not row.get("valid", True):
            invalid += 1
            continue
        campaign_precision = row.get("prediction_precision")
        if isinstance(campaign_precision, (int, float)):
            campaign_precisions.append(float(campaign_precision))
        for edit in row.get("edits") or ():
            kind = str(edit.get("kind") or "unknown")
            bucket = kinds.setdefault(kind, {"edits": 0, "verdicts": {}, "_p": []})
            bucket["edits"] += 1
            verdict = str(edit.get("verdict") or "unknown")
            bucket["verdicts"][verdict] = bucket["verdicts"].get(verdict, 0) + 1
            precision = edit.get("prediction_precision")
            if isinstance(precision, (int, float)):
                bucket["_p"].append(float(precision))
    for bucket in kinds.values():
        values = bucket.pop("_p")
        bucket["mean_precision"] = sum(values) / len(values) if values else None
    return {
        "campaigns": campaigns,
        "invalid": invalid,
        "edits": sum(b["edits"] for b in kinds.values()),
        "kinds": kinds,
        "overall_precision": (sum(campaign_precisions) / len(campaign_precisions))
        if campaign_precisions else None,
    }
