"""失败轨迹 → 技能条目编译器（Evo-Harness 式 harness 进化）。

设计来源：arXiv:2608.15071 *Context-to-Harness Skill Compilation for
Self-Evolving Agents*。原文两阶段：只对失败/负反馈做 execution reflection
产出候选记忆，再在批级做 harness evolution（Add/Merge/Revise/Skip），
并把 harness 分成 general（跨任务共享）与 topic（任务型）两层，最后按注入
预算 b 选择条目注入 solver 提示。

本模块只做文本 guidance 层（与 skill_registry 的可执行技能注册表互补）：
条目是「教训 + 触发条件 + 证据 + 作用域」四要素，不含代码。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Sequence

# 触发词里剔除的噪声词（长度与常见停用词双重过滤）
_STOPWORDS = frozenset({
    "when", "then", "than", "that", "this", "with", "from", "into", "over",
    "the", "and", "for", "was", "were", "are", "has", "have", "had", "but",
    "not", "you", "your", "its", "it's", "all", "any", "can", "cannot",
})


@dataclass(frozen=True)
class GuidanceEntry:
    """一条可注入 solver 提示的技能条目。

    lesson    —— 一句话教训（失败原句归一后的表述）
    trigger   —— 触发词串，用于相关性排序
    scope     —— 作用域描述（topic 层=任务类型；general 层=cross-task）
    layer     —— "general"（跨实例复现）或 "topic"（单次/任务型）
    task_type —— topic 层的任务类型；general 层为空串
    support   —— 该教训被观察到的次数
    trace_ids —— 证据轨迹 id（按观察顺序）
    evidence  —— 逐条证据（trace_id / failure / context）
    """

    lesson: str
    trigger: str
    scope: str
    layer: str
    task_type: str
    support: int
    trace_ids: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]

    def cost(self) -> int:
        """注入成本：lesson 与 trigger 都要写进提示，按字符计。"""
        return len(self.lesson) + len(self.trigger)


def _normalize_lesson(text: str) -> str:
    """归一口径：小写 + 折叠空白，作为合并键（不改写展示用的 lesson 原文）。"""
    return " ".join(str(text).lower().split())


def _keywords(*chunks: str) -> list[str]:
    out: list[str] = []
    for chunk in chunks:
        for token in str(chunk).lower().replace("/", " ").replace("_", " ").split():
            token = token.strip(".,:;()[]{}\"'")
            if len(token) > 3 and token not in _STOPWORDS and token not in out:
                out.append(token)
    return out


def _compile_one(trajectory: dict[str, Any]) -> GuidanceEntry | None:
    failure = str(trajectory.get("failure") or "").strip()
    if not failure:
        return None
    task_type = str(trajectory.get("task_type") or "")
    context = trajectory.get("context") or {}
    ctx_text = " ".join(f"{k} {v}" for k, v in context.items())
    trigger = " ".join(_keywords(failure, task_type, ctx_text))
    return GuidanceEntry(
        lesson=failure,
        trigger=trigger,
        scope=task_type or "cross-task",
        layer="topic",
        task_type=task_type,
        support=1,
        trace_ids=(str(trajectory.get("trace_id") or ""),),
        evidence=({"trace_id": str(trajectory.get("trace_id") or ""),
                   "failure": failure, "context": dict(context)},),
    )


def compile_entries(trajectories: Iterable[dict[str, Any]]) -> list[GuidanceEntry]:
    """把一批轨迹编译成技能条目：跳过通过的，合并同类失败，按 support 分层。

    分层口径：support >= 2 说明该失败在不同实例上复现，升入 general 层
    （跨任务共享）；只观察到一次的留在 topic 层（任务型，待更多证据）。
    """
    merged: dict[str, GuidanceEntry] = {}
    order: list[str] = []
    for trajectory in trajectories:
        if trajectory.get("passed"):
            continue
        entry = _compile_one(trajectory)
        if entry is None:
            continue
        key = _normalize_lesson(entry.lesson)
        if key in merged:
            old = merged[key]
            merged[key] = replace(
                old,
                support=old.support + 1,
                trace_ids=old.trace_ids + entry.trace_ids,
                evidence=old.evidence + entry.evidence,
            )
        else:
            merged[key] = entry
            order.append(key)

    entries: list[GuidanceEntry] = []
    for key in order:
        entry = merged[key]
        if entry.support >= 2:
            entry = replace(entry, layer="general", task_type="", scope="cross-task")
        entries.append(entry)
    return entries


def select_entries(task_text: str, entries: Sequence[GuidanceEntry],
                   budget_chars: int) -> list[GuidanceEntry]:
    """按触发词相关性排序，在注入预算内贪心选取条目。

    预算按 entry.cost()（lesson + trigger 字符数）累加，超出即停；
    预算为 0 或非正时返回空列表（不注入任何条目）。
    """
    if budget_chars <= 0 or not entries:
        return []
    haystack = str(task_text).lower()

    def relevance(entry: GuidanceEntry) -> tuple[int, int]:
        hits = sum(1 for token in entry.trigger.split() if token in haystack)
        # 相关性主序；同分时 support 高者优先（证据更强）
        return (hits, entry.support)

    picked: list[GuidanceEntry] = []
    used = 0
    for entry in sorted(entries, key=relevance, reverse=True):
        cost = entry.cost()
        if used + cost > budget_chars:
            continue
        picked.append(entry)
        used += cost
    return picked


def evolve_harness(harness: Sequence[GuidanceEntry],
                   candidates: Sequence[GuidanceEntry]
                   ) -> dict[str, Any]:
    """批级 harness 进化：Add 新教训、Revise 已有教训（累加证据）、Skip 空批。

    返回 {"harness": [...], "operations": [...]}。operations 逐条记录本次
    编辑动作，便于下游（如 change_manifest 的对账）追溯是哪批失败改了什么。
    """
    current = list(harness)
    if not candidates:
        return {"harness": current,
                "operations": [{"op": "skip", "reason": "no_candidates"}]}

    index = {_normalize_lesson(e.lesson): i for i, e in enumerate(current)}
    operations: list[dict[str, Any]] = []
    for candidate in candidates:
        key = _normalize_lesson(candidate.lesson)
        if key in index:
            position = index[key]
            old = current[position]
            current[position] = replace(
                old,
                support=old.support + candidate.support,
                trace_ids=old.trace_ids + candidate.trace_ids,
                evidence=old.evidence + candidate.evidence,
            )
            operations.append({"op": "revise", "lesson": candidate.lesson,
                               "support": current[position].support})
        else:
            index[key] = len(current)
            current.append(candidate)
            operations.append({"op": "add", "lesson": candidate.lesson,
                               "support": candidate.support})
    return {"harness": current, "operations": operations}


def render_block(entries: Sequence[GuidanceEntry]) -> str:
    """把选中的条目渲染成可直接拼进 solver 提示的文本块（空则空串）。"""
    if not entries:
        return ""
    lines = ["## Learned skills (from prior failures)"]
    for entry in entries:
        lines.append(f"- [{entry.layer}] {entry.lesson} (support={entry.support})")
    return "\n".join(lines)
