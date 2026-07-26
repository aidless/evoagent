from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .workflow import Plan, StepResult, execute_plan

NON_RECOVERABLE = {
    "sandbox_required",
    "human_approval_required",
    "safety_violation",
    "blocked_by_dependency",
}


@dataclass(frozen=True)
class RecoveryStrategy:
    id: str
    status_to_action: dict[str, str]
    allowed_actions: frozenset[str]
    max_replans: int = 2
    max_attempts_per_step: int = 2
    description: str = ""


class RecoveryPolicy(RecoveryStrategy):
    """Backward-compatible unnamed strategy used by workflow callers."""

    def __init__(
        self,
        status_to_action: dict[str, str],
        allowed_actions: frozenset[str],
        max_replans: int = 2,
        max_attempts_per_step: int = 2,
        description: str = "",
    ) -> None:
        super().__init__(
            "inline-policy",
            status_to_action,
            allowed_actions,
            max_replans,
            max_attempts_per_step,
            description,
        )


def execute_with_strategy(
    plan: Plan,
    handlers: dict,
    strategy: RecoveryStrategy,
    replans_tracker: dict | None = None,
    on_step=None,
):
    replans = replans_tracker if replans_tracker is not None else {"n": 0}
    wrapped = {}

    for original_action, original_handler in handlers.items():
        def make(action, handler):
            def run(step, ctx):
                current_action = action
                current_handler = handler
                trace = []
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        result = current_handler(step, ctx)
                    except Exception as exc:
                        result = StepResult(
                            step.id,
                            False,
                            status="executor_error",
                            details={"error": f"{type(exc).__name__}: {exc}"},
                        )
                    trace.append(
                        {
                            "attempt": attempt,
                            "action": current_action,
                            "status": result.status,
                            "passed": result.passed,
                        }
                    )
                    if (
                        result.passed
                        or result.safety_violations
                        or result.status in NON_RECOVERABLE
                    ):
                        break
                    next_action = strategy.status_to_action.get(result.status)
                    if (
                        not next_action
                        or next_action not in strategy.allowed_actions
                        or replans["n"] >= strategy.max_replans
                        or attempt >= strategy.max_attempts_per_step
                    ):
                        break
                    replans["n"] += 1
                    if next_action == "retry_same":
                        current_action = action
                        current_handler = handler
                    else:
                        next_handler = handlers.get(next_action)
                        if not next_handler:
                            break
                        current_action = next_action
                        current_handler = next_handler

                details = {
                    **result.details,
                    "recovery_trace": trace,
                    "replans_used": replans["n"],
                    "strategy_id": strategy.id,
                }
                return StepResult(
                    result.step_id,
                    result.passed,
                    result.output,
                    result.cost,
                    result.latency_s,
                    result.safety_violations,
                    result.status,
                    details,
                )

            return run

        wrapped[original_action] = make(original_action, original_handler)

    result = execute_plan(plan, wrapped)
    # Surface the aggregate budget use in the workflow audit record.
    details = {**result.outcome.details, "replans_used": replans["n"]}
    outcome = type(result.outcome)(
        result.outcome.task_id,
        result.outcome.passed,
        result.outcome.score,
        result.outcome.cost,
        result.outcome.latency_s,
        result.outcome.safety_violations,
        result.outcome.capabilities,
        details,
    )
    result = type(result)(result.plan, result.steps, outcome, result.output)
    if on_step is not None:
        on_step(result)
    return result


def execute_with_recovery(plan: Plan, handlers: dict, policy: RecoveryPolicy, **kwargs):
    """Compatibility entrypoint for the original policy API."""
    return execute_with_strategy(plan, handlers, policy, **kwargs)


class RecoveryRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.data = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.exists()
            else {"strategies": {}, "history": []}
        )

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, self.path)

    def register(self, strategy: RecoveryStrategy, level="experimental"):
        if strategy.id in self.data["strategies"]:
            raise ValueError("strategy id already exists")
        row = {
            "id": strategy.id,
            "status_to_action": strategy.status_to_action,
            "allowed_actions": sorted(strategy.allowed_actions),
            "max_replans": strategy.max_replans,
            "max_attempts_per_step": strategy.max_attempts_per_step,
            "description": strategy.description,
            "level": level,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.data["strategies"][strategy.id] = row
        self.data["history"].append(
            {"action": "register", "strategy_id": strategy.id, "at": row["created_at"]}
        )
        self._save()

    def get(self, strategy_id):
        return self.data["strategies"].get(strategy_id)

    def list(self):
        return sorted(self.data["strategies"].keys())

    def audit(self, limit=20):
        return {
            "strategies": [
                {"id": key, "level": value["level"]}
                for key, value in self.data["strategies"].items()
            ],
            "history": self.data["history"][-limit:],
        }
