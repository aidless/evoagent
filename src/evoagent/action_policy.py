from __future__ import annotations

import hashlib
import json
import ntpath
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    IRREVERSIBLE = "irreversible"
    PRIVILEGE_CHANGE = "privilege_change"
    TRUST_ROOT_CHANGE = "trust_root_change"


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    tool: str
    arguments: dict[str, Any]
    filesystem_scope: tuple[str, ...] = ()
    network_scope: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    reversible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id or not self.tool:
            raise ValueError("action_id and tool are required")
        if not isinstance(self.arguments, dict):
            raise ValueError("arguments must be an object")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")

    @property
    def arguments_sha256(self) -> str:
        raw = json.dumps(self.arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class PolicyDecision:
    action_id: str
    effect: PolicyEffect
    risk: RiskLevel
    reasons: tuple[str, ...]
    arguments_sha256: str
    requires_approval: bool

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["effect"] = self.effect.value
        data["risk"] = self.risk.value
        data["reasons"] = list(self.reasons)
        return data


TRUST_ROOT_PATTERNS = (r"hidden[ _-]?benchmark", r"private[ _-]?key", r"signing[ _-]?key", r"modify.{0,20}evaluator", r"modify.{0,20}promotion")
TRUST_ROOT_KEYS = {
    "promotion_gate", "stage_gates", "hidden_benchmarks", "trusted_keys",
    "private_key", "signatures", "evaluator", "safety_gate", "audit",
}
PRIVILEGE_PATTERNS = (
    r"\bchmod\b", r"\bchown\b", r"set-acl", r"runas", r"administrator",
    r"disable.{0,20}(safety|guard|firewall|approval)", r"bypass.{0,20}(approval|policy|gate)",
)
IRREVERSIBLE_PATTERNS = (
    r"\brm\s+-rf\b", r"remove-item.{0,20}-recurse", r"format\s+[a-z]:",
    r"drop\s+(table|database)", r"delete\s+from", r"shutdown", r"wipe",
)
EXTERNAL_TOOLS = {"send_email", "publish", "deploy", "payment", "browser_submit", "external_api"}
READ_ONLY_TOOLS = {"read_file", "search", "list", "view_image", "get", "query", "inspect"}


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _flat_text(request: ActionRequest) -> str:
    return (request.tool + " " + json.dumps(request.arguments, ensure_ascii=False, default=str)).lower()


def classify_action(request: ActionRequest) -> tuple[RiskLevel, tuple[str, ...]]:
    text = _flat_text(request)
    keys = set(_walk_keys(request.arguments))
    if request.tool.lower() in READ_ONLY_TOOLS and not request.filesystem_scope and not request.network_scope:
        return RiskLevel.READ_ONLY, ("read_only_tool",)
    if keys & TRUST_ROOT_KEYS or any(name in text for name in TRUST_ROOT_KEYS) or any(re.search(pattern,text,re.I) for pattern in TRUST_ROOT_PATTERNS):
        return RiskLevel.TRUST_ROOT_CHANGE, ("trust_root_or_evaluator_change",)
    if any(re.search(pattern, text, re.I) for pattern in PRIVILEGE_PATTERNS):
        return RiskLevel.PRIVILEGE_CHANGE, ("privilege_or_policy_bypass",)
    if not request.reversible or any(re.search(pattern, text, re.I) for pattern in IRREVERSIBLE_PATTERNS):
        return RiskLevel.IRREVERSIBLE, ("irreversible_or_destructive_action",)
    if request.tool.lower() in EXTERNAL_TOOLS or request.network_scope:
        return RiskLevel.EXTERNAL_SIDE_EFFECT, ("external_side_effect",)
    if request.filesystem_scope or any(token in request.tool.lower() for token in ("write", "edit", "patch", "create")):
        return RiskLevel.REVERSIBLE_WRITE, ("workspace_write",)
    return RiskLevel.EXTERNAL_SIDE_EFFECT, ("unknown_tool_fails_closed",)


@dataclass(frozen=True)
class ActionPolicy:
    max_auto_cost: float = 1.0
    allowed_write_roots: tuple[str, ...] = ()

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        risk, reasons = classify_action(request)
        extra = list(reasons)
        if request.estimated_cost > self.max_auto_cost:
            extra.append("cost_requires_approval")
        if risk in {RiskLevel.TRUST_ROOT_CHANGE, RiskLevel.PRIVILEGE_CHANGE}:
            effect = PolicyEffect.DENY
        elif risk in {RiskLevel.IRREVERSIBLE, RiskLevel.EXTERNAL_SIDE_EFFECT} or request.estimated_cost > self.max_auto_cost:
            effect = PolicyEffect.APPROVE
        elif risk is RiskLevel.REVERSIBLE_WRITE and self.allowed_write_roots:
            def within(path: str, root: str) -> bool:
                try:
                    normalized_path = ntpath.normcase(ntpath.abspath(path))
                    normalized_root = ntpath.normcase(ntpath.abspath(root))
                    return ntpath.commonpath((normalized_path, normalized_root)) == normalized_root
                except ValueError:
                    return False
            outside = [p for p in request.filesystem_scope if not any(within(p, root) for root in self.allowed_write_roots)]
            if outside:
                effect = PolicyEffect.DENY
                extra.append("filesystem_scope_outside_allowlist")
            else:
                effect = PolicyEffect.ALLOW
        else:
            effect = PolicyEffect.ALLOW
        return PolicyDecision(
            request.action_id, effect, risk, tuple(extra), request.arguments_sha256,
            effect is PolicyEffect.APPROVE,
        )
