from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .core import save_json
from .web_learning import WebKnowledgeStore

ARCHITECTURE_MAP = {
    "reflection_memory": {
        "terms": ("reflection", "reflexion", "memory stream", "experience"),
        "components": ("experience.py", "autonomy.py"),
        "control": "Only evaluator-grounded feedback enters reusable mutation statistics.",
    },
    "search_and_planning": {
        "terms": ("tree search", "tree of thoughts", "planning", "evolutionary search"),
        "components": ("autonomy.py", "promotion_gate.py"),
        "control": "Bound branching, depth, wall time, and evaluate candidates on a fixed task set.",
    },
    "tool_and_interface_learning": {
        "terms": ("toolformer", "tool use", "interface", "action space"),
        "components": ("workflow.py", "workflow_handlers.py", "shadow_runner.py"),
        "control": "Measure selection, arguments, execution, grounding, and side effects separately.",
    },
    "curriculum_and_skills": {
        "terms": ("curriculum", "skill library", "lifelong learning", "open-ended"),
        "components": ("curriculum.py", "skill_registry.py", "version_registry.py"),
        "control": "Curriculum may change training exposure, never frozen regression or hidden gates.",
    },
    "objective_generation": {
        "terms": ("reward design", "reward function", "objective"),
        "components": ("promotion_gate.py", "protocol.py"),
        "control": "Generated objectives are untrusted artifacts; safety and capability constraints stay external.",
    },
    "uncertainty_and_abstention": {
        "terms": ("calibration", "uncertainty", "selective prediction", "know what they know", "abstain"),
        "components": ("protocol.py", "router.py", "promotion_gate.py"),
        "control": "Measure calibration and selective risk; low confidence must abstain or route to safer tools.",
    },
    "process_verification": {
        "terms": ("process supervision", "step-level reward", "reasoning step", "rationale"),
        "components": ("workflow.py", "promotion_gate.py", "claim_validator.py"),
        "control": "Verify intermediate steps separately from final answers and test verifier robustness.",
    },
    "contamination_control": {
        "terms": ("pretraining data", "contamination", "data leakage", "test overfitting"),
        "components": ("benchmark_registry.py", "attestation.py", ".ci/audit.py"),
        "control": "Track benchmark provenance, temporal splits, and overlap checks before accepting gains.",
    },
    "memory_governance": {
        "terms": ("long context", "memory", "context understanding", "stepwise planners"),
        "components": ("experience.py", "knowledge.py", "knowledge_cards.py"),
        "control": "Evaluate retrieval precision, stale-memory harm, privacy, and long-context robustness independently.",
    },
    "latent_risk": {
        "terms": ("sleeper agents", "deceptive", "backdoor", "hidden trigger", "agent security"),
        "components": ("shadow.py", "attestation.py", "version_registry.py"),
        "control": "Promotion requires trigger-oriented safety tests and post-deployment shadow monitoring, not only clean-task accuracy.",
    },    "real_world_evaluation": {
        "terms": ("benchmark", "github issues", "software engineering", "real-world"),
        "components": ("benchmark_registry.py", "shadow.py", ".ci/audit.py"),
        "control": "Use contamination-aware, reproducible tasks and preserve execution traces.",
    },
}


def _supports(source: dict[str, Any], terms: tuple[str, ...]) -> bool:
    text = (source.get("title", "") + " " + source.get("abstract", "")).lower()
    return any(term in text for term in terms)


def build_evidence_map(store: WebKnowledgeStore) -> dict[str, Any]:
    claims = []
    for claim_id, spec in ARCHITECTURE_MAP.items():
        sources = [
            source_id
            for source_id, source in store.data["sources"].items()
            if _supports(source, spec["terms"])
        ]
        claims.append(
            {
                "claim_id": claim_id,
                "claim": spec["control"],
                "components": list(spec["components"]),
                "sources": sorted(sources),
                "support_count": len(sources),
                "status": "supported" if sources else "gap",
                "automatic_activation": False,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "claims": claims,
        "coverage": {
            "total": len(claims),
            "supported": sum(x["status"] == "supported" for x in claims),
            "gaps": [x["claim_id"] for x in claims if x["status"] == "gap"],
        },
    }


def build_deep_digest(store: WebKnowledgeStore) -> dict[str, Any]:
    evidence = build_evidence_map(store)
    source_index = store.data["sources"]
    prioritized = sorted(
        evidence["claims"],
        key=lambda row: (row["support_count"], row["claim_id"]),
    )
    recommendations = []
    for claim in prioritized:
        recommendations.append(
            {
                "area": claim["claim_id"],
                "evidence_strength": claim["support_count"],
                "recommendation": claim["claim"],
                "implementation_targets": claim["components"],
                "gate": "proposal_only_until_benchmark_passes",
            }
        )
    payload = {
        "schema_version": 1,
        "source_count": len(source_index),
        "card_count": len(store.data["cards"]),
        "evidence": evidence,
        "recommendations": recommendations,
        "provenance_sha256": hashlib.sha256(
            json.dumps(source_index, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "limitations": [
            "Most sources are preprints; claims are architecture guidance, not established guarantees.",
            "Abstract-level extraction can miss qualifications in full text.",
            "Evidence count is not effect size and does not replace controlled ablation.",
            "No learned recommendation may alter trust roots, hidden tests, or safety gates directly.",
        ],
    }
    return payload


def write_deep_digest(root: Path) -> dict[str, Any]:
    store = WebKnowledgeStore(root / ".evo" / "knowledge" / "web-learning.json")
    payload = build_deep_digest(store)
    save_json(root / ".evo" / "knowledge" / "deep-evidence-map.json", payload)
    return payload
