from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import save_json

PATTERNS = {
    "memory": ("memory", "episodic", "long-term", "context"),
    "reflection": ("reflection", "self-refine", "feedback", "critique"),
    "planning": ("planning", "planner", "tree search", "reasoning"),
    "tools": ("tool", "function calling", "mcp", "action"),
    "multi_agent": ("multi-agent", "multi agent", "swarm", "orchestration"),
    "evaluation": ("benchmark", "evaluation", "eval", "test"),
    "safety": ("safety", "security", "sandbox", "permission"),
    "evolution": ("evolution", "self-improv", "self-learning", "optimization"),
    "rag": ("retrieval", "rag", "knowledge base"),
}


def _topics(text: str) -> list[str]:
    low = text.lower()
    return [name for name, terms in PATTERNS.items() if any(term in low for term in terms)]


def synthesize(root: Path) -> dict[str, Any]:
    base = root / ".evo" / "research-100x100"
    papers = json.loads((base / "papers.json").read_text(encoding="utf-8-sig"))["papers"]
    repos = json.loads((base / "repositories.json").read_text(encoding="utf-8-sig"))["repositories"]
    paper_topics = Counter()
    repo_topics = Counter()
    evidence: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"papers": [], "repositories": []})
    for paper in papers:
        text = paper["title"] + " " + paper["abstract"]
        for topic in _topics(text):
            paper_topics[topic] += 1
            evidence[topic]["papers"].append(paper["work_id"])
    for repo in repos:
        readme = ""
        path = Path(repo["path"])
        for name in ("README.md", "README.rst", "README.txt", "README"):
            candidate = path / name
            if candidate.exists() and candidate.stat().st_size <= 2_000_000:
                readme = candidate.read_text(encoding="utf-8", errors="replace")[:100_000]
                break
        text = repo["full_name"] + " " + (repo.get("description") or "") + " " + readme
        for topic in _topics(text):
            repo_topics[topic] += 1
            evidence[topic]["repositories"].append(repo["full_name"])
    cross = []
    for topic in sorted(set(paper_topics) | set(repo_topics)):
        p, r = paper_topics[topic], repo_topics[topic]
        cross.append(
            {
                "topic": topic,
                "paper_support": p,
                "repository_support": r,
                "maturity": "high" if p >= 10 and r >= 10 else "medium" if p >= 3 and r >= 3 else "low",
                "sample_papers": evidence[topic]["papers"][:5],
                "sample_repositories": evidence[topic]["repositories"][:5],
            }
        )
    recommendations = [
        {
            "priority": "P0",
            "proposal": "Repair release integrity before autonomous production promotion.",
            "evidence": ["safety", "evaluation"],
            "targets": ["bundle_signer.py", "bundle.py", ".github/workflows/audit.yml"],
        },
        {
            "priority": "P1",
            "proposal": "Adopt typed candidate schemas and capability-based tool permissions.",
            "evidence": ["tools", "safety"],
            "targets": ["core.py", "workflow.py", "skill_registry.py"],
        },
        {
            "priority": "P1",
            "proposal": "Separate discovery evaluation, hidden confirmation, trigger safety, and shadow evidence.",
            "evidence": ["evaluation", "evolution"],
            "targets": ["autonomy.py", "promotion_gate.py", "shadow.py"],
        },
        {
            "priority": "P1",
            "proposal": "Evaluate memory retrieval quality and stale-memory harm before reusing experience patches.",
            "evidence": ["memory", "reflection"],
            "targets": ["experience.py", "knowledge.py"],
        },
        {
            "priority": "P2",
            "proposal": "Benchmark bounded planning against linear baselines under equal cost and latency budgets.",
            "evidence": ["planning"],
            "targets": ["autonomy.py", "workflow.py"],
        },
    ]
    payload = {
        "schema_version": 1,
        "corpus": {
            "papers": len(papers),
            "repositories": len(repos),
            "repository_bytes": sum(x.get("bytes", 0) for x in repos),
            "repositories_executed": sum(bool(x.get("executed")) for x in repos),
        },
        "paper_topics": dict(paper_topics.most_common()),
        "repository_topics": dict(repo_topics.most_common()),
        "cross_evidence": sorted(cross, key=lambda x: (x["maturity"], x["paper_support"] + x["repository_support"]), reverse=True),
        "recommendations": recommendations,
        "limitations": [
            "Repository analysis is static and README-centric; downloaded code was not executed.",
            "OpenAlex relevance ranking and GitHub metadata can include false positives.",
            "License metadata marked UNKNOWN or NOASSERTION requires manual review before reuse.",
            "Corpus frequency is not causal evidence; recommendations still require controlled experiments.",
        ],
    }
    save_json(base / "deep-synthesis.json", payload)
    return payload
