from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .core import load_json, save_json

RUN_STATUSES = {"queued", "running", "sleeping", "blocked", "completed", "failed", "rolled_back"}
TERMINAL_STATUSES = {"completed", "failed", "rolled_back"}


@dataclass(frozen=True)
class RunBudget:
    max_wall_time_s: float = 14400
    max_tokens: int = 500000
    max_cost_usd: float = 5.0
    max_tool_calls: int = 200
    max_retries: int = 3
    max_consecutive_failures: int = 2


@dataclass(frozen=True)
class RunUsage:
    started_at_epoch: float = field(default_factory=time.time)
    tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
    retries: int = 0
    consecutive_failures: int = 0


@dataclass(frozen=True)
class RunState:
    run_id: str
    agent_id: str
    goal_id: str
    status: str = "queued"
    checkpoint_id: str = ""
    lease_owner: str = ""
    lease_expires_at: float = 0.0
    last_heartbeat: float = 0.0
    next_wakeup_at: float = 0.0
    attempt: int = 0
    last_completed_action: str = ""
    pending_action: str = ""
    idempotency_key: str = ""
    budget: RunBudget = field(default_factory=RunBudget)
    usage: RunUsage = field(default_factory=RunUsage)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.run_id or not self.agent_id or not self.goal_id:
            raise ValueError("run identity is required")
        if self.status not in RUN_STATUSES:
            raise ValueError("invalid run status")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        value = dict(data)
        value["budget"] = RunBudget(**value.get("budget", {}))
        value["usage"] = RunUsage(**value.get("usage", {}))
        return cls(**value)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise ValueError("invalid run_id")
        return self.root / f"{run_id}.json"

    def create(self, state: RunState) -> RunState:
        path = self.path(state.run_id)
        if path.exists():
            raise ValueError("run already exists")
        save_json(path, state.as_dict())
        return state

    def get(self, run_id: str) -> RunState:
        return RunState.from_dict(load_json(self.path(run_id)))

    def save(self, state: RunState) -> RunState:
        save_json(self.path(state.run_id), state.as_dict())
        return state

    def update(self, run_id: str, **changes: Any) -> RunState:
        current = self.get(run_id)
        if current.status in TERMINAL_STATUSES and changes.get("status", current.status) != current.status:
            raise ValueError("terminal run cannot transition")
        return self.save(replace(current, **changes))

    def list(self, status: str | None = None) -> list[RunState]:
        rows = [RunState.from_dict(load_json(path)) for path in self.root.glob("*.json")]
        return sorted((row for row in rows if status is None or row.status == status), key=lambda row: row.run_id)
