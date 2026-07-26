from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMAS = {
    "prompt": {
        "allowed": {"system_prompt", "prompt_strategy", "output_format"},
        "required": set(),
    },
    "router": {
        "allowed": {"tool_router", "routing_thresholds", "fallback"},
        "required": set(),
    },
    "recovery": {
        "allowed": {"recovery_policy", "retry_budget", "fallback_order"},
        "required": set(),
    },
    "workflow": {
        "allowed": {"workflow", "step_budget", "tool_budget"},
        "required": set(),
    },
    "strategy": {
        "allowed": {
            "normalize_case",
            "trim_whitespace",
            "system_prompt",
            "prompt_strategy",
            "output_format",
            "tool_router",
            "routing_thresholds",
            "fallback",
            "recovery_policy",
            "retry_budget",
            "fallback_order",
            "workflow",
            "step_budget",
            "tool_budget",
        },
        "required": set(),
    },
}

IMMUTABLE_KEYS = {
    "safety_gate",
    "promotion_gate",
    "statistical_gate",
    "hidden_benchmarks",
    "trusted_keys",
    "private_key",
    "signatures",
    "audit",
    "autonomy_policy",
    "evaluator_command",
    "proposer_command",
    "post_evolution_intelligence_command",
    "network_allowlist",
    "permissions",
}


def _walk_keys(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield str(key), path
            yield from _walk_keys(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{prefix}[{index}]")


def validate_candidate(candidate: Any, kind: str = "strategy") -> dict:
    if not isinstance(candidate, dict):
        return {"valid": False, "reason": "candidate_not_object", "violations": []}
    schema = SCHEMAS.get(kind)
    if schema is None:
        return {"valid": False, "reason": "unknown_candidate_kind", "violations": [kind]}
    violations = []
    forbidden = [path for key, path in _walk_keys(candidate) if key.lower() in IMMUTABLE_KEYS]
    violations.extend(f"immutable:{path}" for path in forbidden)
    unknown = sorted(set(candidate) - schema["allowed"])
    violations.extend(f"unknown_top_level:{key}" for key in unknown)
    missing = sorted(schema["required"] - set(candidate))
    violations.extend(f"missing:{key}" for key in missing)
    return {
        "valid": not violations,
        "reason": "ok" if not violations else "candidate_schema_violation",
        "kind": kind,
        "violations": violations,
    }
