from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import save_json

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
DEFAULT_TOPICS = (
    "self-improving language model",
    "language agent reflection",
    "evolutionary prompt optimization",
    "automatic curriculum language model",
    "LLM agent evaluation safety",
)
RELEVANCE_TERMS = {
    "agent",
    "language model",
    "llm",
    "self-improv",
    "self-refin",
    "reflection",
    "reflexion",
    "evolution",
    "prompt optimization",
    "curriculum",
    "benchmark",
    "evaluation",
    "safety",
    "interface",
    "tool use",
    "computer interface",
    "tool",
    "reward design",
    "bootstrapping reasoning",
    "lifelong learning",
    "open-ended",
}


@dataclass(frozen=True)
class Paper:
    paper_id: str
    title: str
    abstract: str
    published: str
    updated: str
    authors: tuple[str, ...]
    categories: tuple[str, ...]
    url: str
    source: str = "arxiv"

    def as_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "published": self.published,
            "updated": self.updated,
            "authors": list(self.authors),
            "categories": list(self.categories),
            "url": self.url,
            "source": self.source,
            "content_sha256": hashlib.sha256(
                (self.title + "\n" + self.abstract).encode()
            ).hexdigest(),
        }


def _text(node, path: str) -> str:
    child = node.find(path, ATOM)
    return re.sub(r"\s+", " ", child.text or "").strip() if child is not None else ""


def parse_arxiv_feed(xml: bytes) -> list[Paper]:
    root = ET.fromstring(xml)
    papers = []
    for entry in root.findall("a:entry", ATOM):
        raw_id = _text(entry, "a:id")
        paper_id = raw_id.rstrip("/").split("/")[-1].split("v", 1)[0]
        authors = tuple(
            _text(author, "a:name") for author in entry.findall("a:author", ATOM)
        )
        categories = tuple(
            category.attrib.get("term", "")
            for category in entry.findall("a:category", ATOM)
            if category.attrib.get("term")
        )
        papers.append(
            Paper(
                paper_id,
                _text(entry, "a:title"),
                _text(entry, "a:summary"),
                _text(entry, "a:published"),
                _text(entry, "a:updated"),
                authors,
                categories,
                raw_id.replace("/abs/", "/abs/"),
            )
        )
    return papers


def fetch_arxiv(query: str, limit: int = 10, timeout: int = 30) -> list[Paper]:
    params = urllib.parse.urlencode(
        {
            "search_query": f'all:"{query}"',
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    request = urllib.request.Request(
        ARXIV_API + "?" + params,
        headers={"User-Agent": "EvoAgent-Research/0.1 (auditable-learning)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_arxiv_feed(response.read())


def relevance(paper: Paper) -> float:
    text = (paper.title + " " + paper.abstract).lower()
    matches = sum(term in text for term in RELEVANCE_TERMS)
    title_matches = sum(term in paper.title.lower() for term in RELEVANCE_TERMS)
    return round(min(1.0, (matches + title_matches) / 6), 4)


def derive_lessons(paper: Paper) -> list[str]:
    text = (paper.title + " " + paper.abstract).lower()
    lessons = []
    if any(x in text for x in ("reflection", "reflexion", "self-refin")):
        lessons.append("Store evaluator-grounded feedback and use it to revise later attempts.")
    if any(x in text for x in ("evolution", "search", "optimization", "mutation")):
        lessons.append("Separate candidate generation from fixed evaluation and bounded selection.")
    if any(x in text for x in ("curriculum", "difficulty", "task generation")):
        lessons.append("Adapt the task curriculum while retaining frozen holdout evaluation.")
    if any(x in text for x in ("benchmark", "evaluation", "judge")):
        lessons.append("Use reproducible multi-dimensional evaluation rather than self-reported quality.")
    if any(x in text for x in ("safety", "risk", "alignment", "governance")):
        lessons.append("Keep safety and governance gates independent from capability optimization.")
    if any(x in text for x in ("interface", "tool use", "computer interface", "action space")):
        lessons.append("Treat agent interfaces and action spaces as evolvable components with isolated tests.")
    if any(x in text for x in ("toolformer", "tool use", "external tools", "api call")):
        lessons.append("Learn tool-use policies from validated demonstrations and measure invocation correctness separately.")
    if any(x in text for x in ("reward design", "reward function", "eureka")):
        lessons.append("Treat generated objectives and reward functions as untrusted code requiring sandboxed evaluation.")
    if any(x in text for x in ("bootstrapping reasoning", "self-taught reasoner", "rationale")):
        lessons.append("Bootstrap only from solutions that pass answer verification, and retain rejected rationales for audit.")
    if any(x in text for x in ("lifelong learning", "open-ended", "skill library", "automatic curriculum")):
        lessons.append("Grow reusable skills with an automatic curriculum while preserving frozen regression tasks.")
    return lessons or ["Treat this work as evidence for review, not as an automatically trusted mutation."]


class WebKnowledgeStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.exists()
            else {"schema_version": 1, "sources": {}, "cards": [], "runs": []}
        )

    def ingest(self, papers: list[Paper], run_id: str, min_relevance: float = 0.25):
        added = 0
        for paper in papers:
            score = relevance(paper)
            if score < min_relevance:
                continue
            source_id = f"arxiv:{paper.paper_id}"
            self.data["sources"][source_id] = paper.as_dict()
            card_id = hashlib.sha256(source_id.encode()).hexdigest()[:16]
            if any(card["card_id"] == card_id for card in self.data["cards"]):
                continue
            self.data["cards"].append(
                {
                    "card_id": card_id,
                    "source_id": source_id,
                    "title": paper.title,
                    "relevance": score,
                    "lessons": derive_lessons(paper),
                    "trust": {
                        "tier": "primary-preprint",
                        "verified_source": True,
                        "automatic_activation": False,
                    },
                    "learned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
            added += 1
        summary = {
            "run_id": run_id,
            "fetched": len(papers),
            "added": added,
            "sources": len(self.data["sources"]),
            "cards": len(self.data["cards"]),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.data["runs"].append(summary)
        save_json(self.path, self.data)
        return summary

    def digest(self) -> dict[str, Any]:
        lesson_counts: dict[str, int] = {}
        for card in self.data["cards"]:
            for lesson in card["lessons"]:
                lesson_counts[lesson] = lesson_counts.get(lesson, 0) + 1
        ranked = sorted(lesson_counts.items(), key=lambda item: (-item[1], item[0]))
        return {
            "sources": len(self.data["sources"]),
            "cards": len(self.data["cards"]),
            "principles": [
                {"principle": lesson, "supporting_sources": count}
                for lesson, count in ranked
            ],
            "activation_policy": "knowledge informs proposals; benchmark and safety gates control activation",
        }


def learn(root: Path, topics=DEFAULT_TOPICS, per_topic: int = 8, timeout: int = 30):
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1_000_000:06d}"
    all_papers: dict[str, Paper] = {}
    errors = []
    for index, topic in enumerate(topics):
        try:
            for paper in fetch_arxiv(topic, per_topic, timeout):
                all_papers[paper.paper_id] = paper
        except Exception as exc:
            errors.append({"topic": topic, "error": f"{type(exc).__name__}: {exc}"})
        if index + 1 < len(topics):
            time.sleep(1.0)
    store = WebKnowledgeStore(root / ".evo" / "knowledge" / "web-learning.json")
    summary = store.ingest(list(all_papers.values()), run_id)
    report = {
        **summary,
        "topics": list(topics),
        "errors": errors,
        "digest": store.digest(),
    }
    save_json(root / ".evo" / "knowledge" / "web-learning-last.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description="Learn auditable knowledge from primary web sources")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--topic", action="append")
    parser.add_argument("--per-topic", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    report = learn(
        args.root.resolve(), args.topic or DEFAULT_TOPICS, args.per_topic, args.timeout
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
