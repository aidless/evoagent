"""change_manifest：AHE 式 per-edit 预测-对账-回滚（P1 核心件）。

设计来源：arXiv:2604.25850 "Agentic Harness Engineering" 的 change manifest 机制——
每次 harness 编辑必须自声明预测（预计修好什么、可能弄坏什么），下一轮把预测与
实际任务级变化对账，产出 per-edit verdict，并按文件粒度给出回滚计划。

与 promotion_gate 的分工：promotion_gate 判"这个候选能不能上位"，
change_manifest 判"候选里的每一笔编辑各自有没有兑现预测"。两者互补：
上位决策看总分，信任度归因看 per-edit verdict。

fail-closed 原则：
- 任务集不一致 → 拒绝产出 verdict（reasons 带 task_set_mismatch）；
- 预测引用不存在的任务 id → 该 edit 判 invalid_prediction（幻觉预测必须显眼）；
- 未预测到的回归单独计数（unanticipated_regressions），不让盲区静默。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import Run


@dataclass(frozen=True)
class ChangeEdit:
    """一笔 harness 编辑及其自声明预测。

    字段对齐 AHE 的组件分类（kind 可取 prompt/tool/middleware/memory/
    workflow/subagent 等，本模块不做枚举限制，交给上层 schema 约束）。
    """
    edit_id: str
    kind: str
    target_files: tuple[str, ...]
    predicted_fix: tuple[str, ...]          # 预期 fail→pass 的任务 id
    predicted_regression: tuple[str, ...]   # 预期有 pass→fail 风险的任务 id
    rationale: str = ""


def validate_edit(edit: ChangeEdit) -> list[str]:
    """校验单笔编辑的声明完整性，返回违规列表（空列表 = 合规）。

    AHE 纪律：没有预测的编辑不允许入账——"改了但不知道为什么改"是事故，
    不是数据。
    """
    violations: list[str] = []
    if not edit.edit_id:
        violations.append("missing_edit_id")
    if not edit.kind:
        violations.append("missing_kind")
    if not edit.target_files:
        violations.append("missing_target_files")
    if not edit.predicted_fix and not edit.predicted_regression:
        violations.append("empty_prediction")
    return violations


def _flips(base: Run, cand: Run) -> tuple[set[str], set[str]]:
    """计算实际翻转：返回 (fixed, regressed) 两个任务 id 集合。"""
    b, c = base.by_task(), cand.by_task()
    fixed = {t for t in b if (not b[t].passed) and c[t].passed}
    regressed = {t for t in b if b[t].passed and (not c[t].passed)}
    return fixed, regressed


def reconcile(base: Run, cand: Run, edits: tuple[ChangeEdit, ...]) -> dict[str, Any]:
    """把每笔编辑的自声明预测与实际任务级变化对账。

    verdict 判定顺序（regression 优先——回归比不生效严重）：
      1. invalid_prediction：编辑声明不合规或预测引用了任务集里不存在的 id；
      2. regression：出现了 pass→fail 翻转（分 anticipated / unanticipated 两桶）；
      3. effective_fix：predicted_fix 与实际 fixed 有交集；
      4. no_effect：预测完全没兑现。

    campaign 级聚合 precision/recall 的口径（对齐 AHE 报告方式）：
      precision = |predicted_fix ∩ fixed| / |predicted_fix|（分母含未命中预测，
      不看分数的编辑进不了分子——这就是"预测质量"而非"结果质量"）。
    """
    # fail-closed 第一道：任务集不一致时拒绝判定任何 verdict
    b, c = base.by_task(), cand.by_task()
    if set(b) != set(c):
        return {"valid": False, "reasons": ["task_set_mismatch"], "edits": {}}

    fixed, regressed = _flips(base, cand)
    all_task_ids = set(b)
    # 盲区对账：没有任何编辑预测到的回归 = campaign 级盲区，
    # 按 AHE 纪律必须显眼——记在所有在场编辑头上（shared blame）。
    covered = set().union(*(set(e.predicted_regression) for e in edits)) if edits else set()
    unanticipated = regressed - covered
    edits_out: dict[str, Any] = {}
    hit_total, predicted_total = 0, 0

    for edit in edits:
        violations = validate_edit(edit)
        unknown = [t for t in (*edit.predicted_fix, *edit.predicted_regression)
                   if t not in all_task_ids]
        if violations or unknown:
            edits_out[edit.edit_id] = {
                "verdict": "invalid_prediction",
                "violations": violations,
                "unknown_task_ids": unknown,
            }
            continue

        # 回归对账：本编辑预测到的回归（own）与全局盲区（shared）分开记
        anticipated = sorted(set(edit.predicted_regression) & regressed)
        hits = sorted(set(edit.predicted_fix) & fixed)

        if anticipated:
            verdict = "regression"
        elif unanticipated:
            verdict = "regression"  # 盲区回归：在场编辑共同承担，不允许静默
        elif hits:
            verdict = "effective_fix"
        else:
            verdict = "no_effect"

        predicted_n = len(edit.predicted_fix)
        if predicted_n:
            predicted_total += predicted_n
            hit_total += len(hits)

        edits_out[edit.edit_id] = {
            "verdict": verdict,
            "files": tuple(edit.target_files),
            "predicted_fix": list(edit.predicted_fix),
            "hits": hits,
            "prediction_precision": (len(hits) / predicted_n) if predicted_n else None,
            "anticipated_regressions": anticipated,
            "unanticipated_regressions": sorted(unanticipated),
        }

    # campaign 级聚合：全 campaign 的 fix 预测精度（AHE 实测 33.7%，随机基线 6.5%）
    campaign = {
        "prediction_precision": (hit_total / predicted_total) if predicted_total else None,
        "total_predicted": predicted_total,
        "total_hit": hit_total,
    }
    return {"valid": True, "edits": edits_out, "campaign": campaign}


def build_rollback_plan(reconcile_result: dict[str, Any],
                        include_no_effect: bool = False) -> dict[str, Any]:
    """按 per-edit verdict 生成文件粒度回滚计划。

    - regression：无条件回滚其 target_files（必须提供文件，validate_edit 已挡空）；
    - no_effect：默认保留观察；include_no_effect=True 时回滚（对齐 AHE"无效即回滚"）；
    - effective_fix / invalid_prediction：保留（invalid 保留是为了留给上层告警处理，
      回滚决定权不在此模块）。
    """
    edits = reconcile_result.get("edits", {})
    rollback: list[dict[str, Any]] = []
    keep: list[str] = []
    for edit_id, info in edits.items():
        verdict = info.get("verdict")
        if verdict in ("regression",) or (include_no_effect and verdict == "no_effect"):
            rollback.append({"edit_id": edit_id, "files": info.get("files", ())})
        else:
            keep.append(edit_id)
    return {"rollback": rollback, "keep": keep}
