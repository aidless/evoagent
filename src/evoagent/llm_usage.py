"""把 LLM 网关响应的 token usage 提取成可落盘的纯数据。

诚实边界（AGENTS.local 第15条 / 用户 m02175）:
- token 数不是钱：这里的字段一律叫 *_tokens，不做任何「token→成本」换算，
  下游也不许把 token 比例写成成本比例。
- usage 是**一次 propose 调用**的批次级读数（一次调用产出多个候选），不是单候选
  成本。attach_usage 把它原样挂到每个候选上并标注 batch_size：下游若要求候选级
  用量，必须自己除以 batch_size 且如实标注这是均摊估计，模块本身不做摊薄。
- 网关不返回 usage 时返回 None，绝不编造 0。
"""
from __future__ import annotations

from typing import Any


def extract_usage(payload: dict[str, Any]) -> dict[str, int] | None:
    """从 OpenAI 兼容 /v1/chat/completions 响应里抽 token 用量；缺则 None。"""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    out: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            out[key] = value
    details = ("prompt_tokens_details", "completion_tokens_details")
    for detail_key, field in zip(details, ("cached_tokens", "reasoning_tokens")):
        block = usage.get(detail_key)
        if isinstance(block, dict) and isinstance(block.get(field), int):
            out[field] = block[field]
    return out or None


def attach_usage(candidates: list[dict[str, Any]], usage: dict[str, int] | None) -> list[dict[str, Any]]:
    """把批次级 usage 挂到每个候选的 proposal_usage 字段，标注 batch_size。

    不改候选原有字段；usage 为 None 时不写该字段（下游落 None，兼容旧账本）。
    """
    if not usage:
        return candidates
    record = dict(usage)
    record["batch_size"] = max(1, len(candidates))
    out = []
    for candidate in candidates:
        item = dict(candidate)
        item["proposal_usage"] = dict(record)
        out.append(item)
    return out
