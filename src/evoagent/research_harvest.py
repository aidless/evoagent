from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from .core import save_json

PAPER_QUERIES = (
    "large language model autonomous agents",
    "self improving language models",
    "language agent reflection memory",
    "evolutionary prompt optimization",
    "automatic design agentic systems",
    "language model tool use function calling",
    "language agent planning tree search",
    "LLM agent benchmark evaluation",
    "language model process supervision reasoning",
    "AI agent safety security prompt injection",
    "long context memory language models",
    "benchmark contamination language models",
)

GITHUB_QUERIES = (
    "topic:llm-agent stars:>50 archived:false",
    "topic:ai-agents stars:>50 archived:false",
    "topic:autonomous-agents stars:>50 archived:false",
    "topic:multi-agent-systems stars:>30 archived:false",
    '"LLM agent" in:name,description stars:>100 archived:false',
    '"prompt optimization" in:name,description stars:>20 archived:false',
    '"agent benchmark" in:name,description stars:>20 archived:false',
    '"RAG agent" in:name,description stars:>100 archived:false',
)


def _abstract(inverted: dict[str, list[int]] | None) -> str:
    if not inverted:
        return ""
    positions = [(index, token) for token, indexes in inverted.items() for index in indexes]
    return " ".join(token for _, token in sorted(positions))


def collect_openalex(target: int = 100, timeout: int = 45) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "EvoAgent-Research/0.1 (auditable-learning)"})
    works: dict[str, dict[str, Any]] = {}
    for query in PAPER_QUERIES:
        cursor = "*"
        for _ in range(3):
            params = {
                "search": query,
                "per-page": 50,
                "cursor": cursor,
                "select": "id,display_name,publication_year,doi,open_access,primary_location,authorships,cited_by_count,abstract_inverted_index,type",
            }
            for attempt in range(5):
                response = session.get("https://api.openalex.org/works", params=params, timeout=timeout)
                if response.status_code == 200:
                    break
                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
            else:
                continue
            payload = response.json()
            for raw in payload.get("results", []):
                abstract = _abstract(raw.get("abstract_inverted_index"))
                title = raw.get("display_name") or ""
                text = (title + " " + abstract).lower()
                terms = ("agent", "language model", "llm", "prompt", "tool", "reasoning", "benchmark")
                relevance = sum(term in text for term in terms)
                if relevance < 2:
                    continue
                wid = raw["id"].rsplit("/", 1)[-1]
                location = raw.get("primary_location") or {}
                source = location.get("source") or {}
                authors = [
                    item.get("author", {}).get("display_name")
                    for item in raw.get("authorships", [])
                    if item.get("author", {}).get("display_name")
                ]
                row = {
                    "work_id": wid,
                    "title": title,
                    "abstract": abstract,
                    "year": raw.get("publication_year"),
                    "doi": raw.get("doi"),
                    "url": location.get("landing_page_url") or raw["id"],
                    "pdf_url": location.get("pdf_url"),
                    "venue": source.get("display_name"),
                    "authors": authors,
                    "citations": raw.get("cited_by_count", 0),
                    "open_access": raw.get("open_access") or {},
                    "type": raw.get("type"),
                    "query": query,
                    "relevance": relevance,
                    "source": "openalex",
                }
                row["content_sha256"] = hashlib.sha256(
                    (title + "\n" + abstract).encode()
                ).hexdigest()
                old = works.get(wid)
                if old is None or (row["relevance"], row["citations"]) > (
                    old["relevance"], old["citations"]
                ):
                    works[wid] = row
            cursor = payload.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.2)
    ranked = sorted(
        works.values(),
        key=lambda row: (row["relevance"], min(row["citations"], 10000), row.get("year") or 0),
        reverse=True,
    )
    return ranked[:target]


def github_candidates(target: int = 100, timeout: int = 45) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(
        {"Accept": "application/vnd.github+json", "User-Agent": "EvoAgent-Research/0.1"}
    )
    token = os.getenv("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    repos: dict[str, dict[str, Any]] = {}
    for query in GITHUB_QUERIES:
        for page in range(1, 4):
            response = session.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 50, "page": page},
                timeout=timeout,
            )
            if response.status_code == 403 and "rate limit" in response.text.lower():
                return sorted(repos.values(), key=lambda x: (x.get("relevance", 0), x["stars"]), reverse=True)[:target]
            response.raise_for_status()
            for raw in response.json().get("items", []):
                if raw.get("fork") or raw.get("archived"):
                    continue
                name_text = (raw["full_name"] + " " + (raw.get("description") or "") + " " + " ".join(raw.get("topics") or [])).lower()
                relevance_terms = ("agent", "llm", "language model", "prompt", "rag", "memory", "tool", "autonomous", "multi-agent", "benchmark")
                repo_relevance = sum(term in name_text for term in relevance_terms)
                if repo_relevance < 2:
                    continue
                row = {
                    "full_name": raw["full_name"],
                    "description": raw.get("description"),
                    "html_url": raw["html_url"],
                    "clone_url": raw["clone_url"],
                    "default_branch": raw.get("default_branch") or "main",
                    "stars": raw.get("stargazers_count", 0),
                    "forks": raw.get("forks_count", 0),
                    "language": raw.get("language"),
                    "license": (raw.get("license") or {}).get("spdx_id"),
                    "updated_at": raw.get("updated_at"),
                    "topics": raw.get("topics") or [],
                    "query": query,
                    "relevance": repo_relevance,
                }
                repos[row["full_name"]] = row
            if len(repos) >= target * 2:
                break
            time.sleep(1.0)
        if len(repos) >= target * 2:
            break
    return sorted(repos.values(), key=lambda x: (x["relevance"], x["stars"], x["forks"]), reverse=True)[:target]


def _tree_hash(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    files = 0
    total = 0
    for file in sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts):
        rel = file.relative_to(path).as_posix().encode()
        size = file.stat().st_size
        digest.update(rel + b"\0" + str(size).encode() + b"\0")
        with file.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        files += 1
        total += size
    return digest.hexdigest(), files, total


def clone_repositories(repos: list[dict[str, Any]], out: Path, timeout: int = 90) -> list[dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for index, repo in enumerate(repos, 1):
        target = out / repo["full_name"].replace("/", "__")
        record = {**repo, "path": str(target), "index": index, "executed": False}
        if not target.exists():
            try:
                proc = subprocess.run(
                    ["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "--no-tags", repo["clone_url"], str(target)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                if proc.returncode != 0:
                    record.update({"status": "clone_failed", "error": proc.stderr[-500:]})
                    results.append(record)
                    continue
            except subprocess.TimeoutExpired:
                record.update({"status": "clone_failed", "error": "timeout"})
                results.append(record)
                continue
        try:
            commit = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            ).stdout.strip()
            tree_hash, file_count, size = _tree_hash(target)
            record.update(
                {
                    "status": "downloaded",
                    "commit": commit,
                    "tree_sha256": tree_hash,
                    "file_count": file_count,
                    "bytes": size,
                }
            )
        except Exception as exc:
            record.update({"status": "inspection_failed", "error": f"{type(exc).__name__}: {exc}"})
        results.append(record)
        print(json.dumps({"repository": repo["full_name"], "status": record["status"], "index": index}))
    return results


def summarize(papers: list[dict[str, Any]], repos: list[dict[str, Any]]) -> dict[str, Any]:
    terms = Counter()
    for paper in papers:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        for term in ("agent", "memory", "reflection", "tool", "planning", "benchmark", "safety", "prompt", "reasoning", "multi-agent"):
            if term in text:
                terms[term] += 1
    return {
        "papers": len(papers),
        "repositories": len(repos),
        "repositories_downloaded": sum(x.get("status") == "downloaded" for x in repos),
        "repository_bytes": sum(x.get("bytes", 0) for x in repos),
        "paper_topics": dict(terms.most_common()),
        "languages": dict(Counter(x.get("language") or "Unknown" for x in repos).most_common()),
        "licenses": dict(Counter(x.get("license") or "UNKNOWN" for x in repos).most_common()),
        "supply_chain_policy": "downloaded as untrusted data; no repository code executed",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--papers", type=int, default=100)
    parser.add_argument("--repos", type=int, default=100)
    parser.add_argument("--repo-list", type=Path)
    parser.add_argument("--skip-clone", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    research = root / ".evo" / "research-100x100"
    papers = collect_openalex(args.papers)
    save_json(research / "papers.json", {"papers": papers, "count": len(papers)})
    repos = (
        json.loads(args.repo_list.read_text(encoding="utf-8-sig"))["repositories"]
        if args.repo_list
        else github_candidates(args.repos)
    )
    save_json(research / "repository-candidates.json", {"repositories": repos, "count": len(repos)})
    downloaded = repos if args.skip_clone else clone_repositories(repos[: args.repos], research / "repositories")
    save_json(research / "repositories.json", {"repositories": downloaded, "count": len(downloaded)})
    summary = summarize(papers, downloaded)
    save_json(research / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
