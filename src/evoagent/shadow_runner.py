from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .protocol import Outcome


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    timeout_seconds: float = 30.0


def _failure(task_id: str, error: str, latency: float) -> Outcome:
    return Outcome(
        task_id,
        False,
        0.0,
        latency_s=latency,
        details={"error": error},
    )


def execute(spec: CommandSpec, task_id: str, input_text: str, shadow_mode: bool):
    """Execute one evaluator command and convert its JSON output to an Outcome."""
    env = os.environ.copy()
    env["SHADOW_MODE"] = "1" if shadow_mode else "0"
    env["EVO_INPUT"] = input_text
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(spec.argv),
            env=env,
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        return None, _failure(task_id, "timeout", elapsed)
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        return None, _failure(task_id, f"process_exit_{proc.returncode}", elapsed)
    try:
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            raise ValueError("top-level JSON must be an object")
    except (json.JSONDecodeError, ValueError) as exc:
        return None, _failure(task_id, f"invalid_output: {exc}", elapsed)

    passed = bool(payload.get("passed", False))
    safety_violations = int(payload.get("safety_violations", 0))
    if payload.get("side_effects"):
        safety_violations += 1
    score = float(payload.get("score", 1.0 if passed else 0.0))
    outcome = Outcome(
        task_id,
        passed and safety_violations == 0,
        score if safety_violations == 0 else 0.0,
        cost=float(payload.get("cost", 0.0)),
        latency_s=elapsed,
        safety_violations=safety_violations,
        capabilities=payload.get("capabilities", {}),
        details={
            "status": payload.get("status", "completed"),
            **({"error": payload["error"]} if "error" in payload else {}),
        },
    )
    return payload.get("output"), outcome


def run_shadow_task(
    recorder,
    task_id: str,
    input_text: str,
    baseline: CommandSpec,
    candidate: CommandSpec,
):
    baseline_output, baseline_outcome = execute(
        baseline, task_id, input_text, shadow_mode=False
    )
    # The candidate is always isolated in shadow mode and its output is never returned.
    _, candidate_outcome = execute(candidate, task_id, input_text, shadow_mode=True)
    recorder.record(task_id, input_text, baseline_outcome, candidate_outcome)
    return {
        "task_id": task_id,
        "user_output": baseline_output,
        "baseline_passed": baseline_outcome.passed,
        "candidate_output_exposed": False,
    }


class ShadowRunner:
    """Legacy model-registry shadow probe retained for existing callers."""

    def __init__(self, registry, out_path: Path):
        self.registry = registry
        self.path = out_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def run(self, cases, backend="hf_snapshot", model_id="qwen2.5-1.5b-instruct"):
        runs = []
        for case in cases:
            started = time.monotonic()
            status = "pending"
            output = None
            error = None
            try:
                from .transformers_backend import runtime_check

                spec = self.registry.get(model_id)
                output = runtime_check(Path(spec["path"]))
                status = "completed" if output.get("available") else "unavailable"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                status = "error"
            runs.append(
                {
                    "case": case,
                    "model": model_id,
                    "duration_s": round(time.monotonic() - started, 2),
                    "status": status,
                    "output": output,
                    "error": error,
                }
            )
        record = {
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "backend": backend,
            "model": model_id,
            "runs": runs,
        }
        self.path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return record
