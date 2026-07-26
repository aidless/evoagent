from __future__ import annotations
import time
from dataclasses import replace
from .durable_run import RunState, RunUsage


def charge(state: RunState, *, tokens: int = 0, cost_usd: float = 0.0, tool_calls: int = 0, retry: bool = False, failure: bool = False) -> RunState:
    if min(tokens, cost_usd, tool_calls) < 0: raise ValueError("usage increments cannot be negative")
    u = state.usage
    usage = replace(u, tokens=u.tokens + tokens, cost_usd=u.cost_usd + cost_usd, tool_calls=u.tool_calls + tool_calls, retries=u.retries + int(retry), consecutive_failures=u.consecutive_failures + 1 if failure else 0)
    return replace(state, usage=usage)


def budget_status(state: RunState, now: float | None = None) -> dict:
    now = now or time.time(); b, u = state.budget, state.usage
    reasons=[]
    if now-u.started_at_epoch>b.max_wall_time_s: reasons.append("wall_time")
    if u.tokens>b.max_tokens: reasons.append("tokens")
    if u.cost_usd>b.max_cost_usd: reasons.append("cost")
    if u.tool_calls>b.max_tool_calls: reasons.append("tool_calls")
    if u.retries>b.max_retries: reasons.append("retries")
    if u.consecutive_failures>b.max_consecutive_failures: reasons.append("consecutive_failures")
    return {"allowed":not reasons,"kill_switch":bool(reasons),"reasons":reasons}
