#!/usr/bin/env python3
"""Recompute the toy-loop trace and compare it to the committed copy.

The trace is the gate / promote / reject / rollback behavior of the shipped
controller on ``examples/benchmark.json`` (4 string cases). It does not call
a model and does not read ``benchmarks/raw/``.

Wall-clock fields are omitted. ``latency_regression`` is dropped from stored
reason lists because a slow machine can add it without changing the decision
on this sample; see FAILURE_MODES.md.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
os.environ["PYTHONPATH"] = str(SRC)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evoagent import __version__
from evoagent.cli import init
from evoagent.core import (
    candidate_id,
    evolve,
    load_json,
    rollback,
    safety_check,
    save_json,
)

EVIDENCE = ROOT / "evidence" / "toy-trace.json"
SOLVED_ID = "f8a196f466db"
SEED_POLICY = {"normalize_case": False, "trim_whitespace": False}
STATE_NAMES = [
    "shipped_config_rejects_score_gain",
    "legacy_gate_promotes_authored_solution",
    "followup_round_no_gain",
    "legacy_gate_promotes_one_case_gain",
    "forbidden_token_caught",
    "forbidden_token_bypass_split_fields",
    "forbidden_token_bypass_double_space",
    "rollback_restores_seed",
    "rollback_installs_tampered_snapshot",
    "rollback_corrupt_snapshot_drops_history",
]


def _dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _stable_eval(result: dict) -> dict:
    return {
        "failures": list(result["failures"]),
        "passed": result["passed"],
        "score": result["score"],
        "total": result["total"],
    }


def _reasons(decision: dict | None) -> list[str] | None:
    if not decision:
        return None
    return [r for r in decision["reasons"] if r != "latency_regression"]


def _candidate_rows(report: dict) -> list[dict]:
    rows = []
    for row in report["candidates"]:
        rows.append(
            {
                "evaluation": _stable_eval(row["evaluation"]),
                "id": row["id"],
                "reason": row["reason"],
                "safe": row["safe"],
            }
        )
    return rows


@contextmanager
def _workspace(cfg: dict):
    temp = tempfile.TemporaryDirectory(prefix="evoagent-toy-")
    try:
        root = Path(temp.name)
        (root / "examples").mkdir()
        (root / "seed.json").write_bytes((ROOT / "seed.json").read_bytes())
        (root / "examples" / "benchmark.json").write_bytes(
            (ROOT / "examples" / "benchmark.json").read_bytes()
        )
        (root / "examples" / "evaluator.py").write_bytes(
            (ROOT / "examples" / "evaluator.py").read_bytes()
        )
        save_json(root / "evo.json", cfg)
        init(root)
        yield root
    finally:
        temp.cleanup()


def _base_cfg() -> dict:
    cfg = load_json(ROOT / "evo.json")
    cfg.pop("post_evolution_intelligence_command", None)
    return cfg


def _decision(report: dict) -> dict:
    decision = report["statistical_decision"]
    out = {
        "active_id": report["active_id"],
        "active_score": report["active_score"],
        "baseline": _stable_eval(report["baseline"]),
        "candidates": _candidate_rows(report),
        "legacy_promoted": report["legacy_promoted"],
        "promoted": report["promoted"],
        "statistical_reasons": _reasons(decision),
    }
    if decision:
        out["mean_gain"] = decision["mean_gain"]
        out["mcnemar_p_value"] = decision["mcnemar"]["p_value"]
        out["bootstrap_ci"] = [round(x, 6) for x in decision["bootstrap_ci"]]
    return out


def _shipped_reject() -> dict:
    cfg = load_json(ROOT / "evo.json")
    # Keep the shipped intelligence command. The temp root has no
    # benchmarks/raw/, so the substep must fail closed rather than score.
    with _workspace(cfg) as root:
        report = evolve(root)
        intel = report.get("intelligence") or {}
        reason = str(intel.get("reason") or "")
        body = _decision(report)
        body["intelligence"] = {
            "mentions_private_gsm8k_file": "gsm8k-test.jsonl" in reason,
            "reason_class": "FileNotFoundError" if "FileNotFoundError" in reason else "other",
            "verified": intel.get("verified"),
        }
        body["name"] = "shipped_config_rejects_score_gain"
        return body


def _legacy_promote_and_followup() -> tuple[dict, dict]:
    cfg = _base_cfg()
    cfg["statistical_gate"]["enabled"] = False
    with _workspace(cfg) as root:
        first = evolve(root)
        promote = _decision(first)
        promote["name"] = "legacy_gate_promotes_authored_solution"
        authored = cfg["mutations"]
        promote["authored_mutation_count"] = len(authored)
        promote["promoted_candidate_equals_authored_mutation"] = (
            load_json(root / ".evo" / "active.json") == {**SEED_POLICY, **authored[-1]}
        )
        second = evolve(root)
        follow = _decision(second)
        follow["name"] = "followup_round_no_gain"
        follow["unique_candidate_ids"] = sorted({row["id"] for row in follow["candidates"]})
        return promote, follow


def _one_case() -> dict:
    cfg = _base_cfg()
    cfg["statistical_gate"]["enabled"] = False
    cfg["mutations"] = [{"normalize_case": True}]
    with _workspace(cfg) as root:
        report = evolve(root)
        body = _decision(report)
        body["name"] = "legacy_gate_promotes_one_case_gain"
        body["min_gain"] = cfg["min_gain"]
        return body


def _safety() -> list[dict]:
    cfg = load_json(ROOT / "evo.json")
    caught_body = {"instruction": "please shutdown /s"}
    split_body = {"cmd": "shutdown", "flag": "/s"}
    spaced_body = {"note": "shutdown  /s"}
    rows = []
    for name, body in (
        ("forbidden_token_caught", caught_body),
        ("forbidden_token_bypass_split_fields", split_body),
        ("forbidden_token_bypass_double_space", spaced_body),
    ):
        safe, reason = safety_check(body, cfg)
        rows.append(
            {
                "candidate": body,
                "name": name,
                "reason": reason,
                "safe": safe,
            }
        )
    return rows


def _rollback_states() -> list[dict]:
    cfg = _base_cfg()
    cfg["statistical_gate"]["enabled"] = False
    states = []

    with _workspace(cfg) as root:
        evolve(root)
        before = sorted((root / ".evo" / "history").glob("*.json"))
        rollback(root)
        states.append(
            {
                "active_equals_seed": load_json(root / ".evo" / "active.json") == SEED_POLICY,
                "name": "rollback_restores_seed",
                "snapshots_after": len(list((root / ".evo" / "history").glob("*.json"))),
                "snapshots_before": len(before),
            }
        )

    with _workspace(cfg) as root:
        evolve(root)
        injected = {"injected": True, "normalize_case": False, "trim_whitespace": False}
        snapshot = sorted((root / ".evo" / "history").glob("*.json"))[-1]
        snapshot.write_text(json.dumps(injected), encoding="utf-8")
        rollback(root)
        restored = load_json(root / ".evo" / "active.json")
        states.append(
            {
                "active_equals_tampered_json": restored == injected,
                "name": "rollback_installs_tampered_snapshot",
                "restored_id": candidate_id(restored),
            }
        )

    with _workspace(cfg) as root:
        evolve(root)
        snapshot = sorted((root / ".evo" / "history").glob("*.json"))[-1]
        snapshot.write_text("{not json", encoding="utf-8")
        error = None
        try:
            rollback(root)
        except json.JSONDecodeError as exc:
            error = type(exc).__name__
        active_text = (root / ".evo" / "active.json").read_text(encoding="utf-8")
        states.append(
            {
                "active_text": active_text,
                "error": error,
                "history_files_remaining": len(list((root / ".evo" / "history").glob("*.json"))),
                "name": "rollback_corrupt_snapshot_drops_history",
            }
        )
    return states


def _json_files_with_token(token: str) -> list[str]:
    listed = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    hits = []
    for raw in listed.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode()
        if rel == "evidence/toy-trace.json" or not rel.endswith((".json", ".jsonl")):
            continue
        path = ROOT / rel
        if token in path.read_text(encoding="utf-8", errors="ignore"):
            hits.append(rel)
    return sorted(hits)


def _consistency() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    badge = re.search(r"\[\!\[CI\]\(([^)]+)\)\]\(([^)]+)\)", readme)
    return {
        "ci_badge_image": badge.group(1) if badge else None,
        "ci_badge_target": badge.group(2) if badge else None,
        "package_version": __version__,
        "pyproject_version_matches": f'version = "{__version__}"' in pyproject,
        "readme_contains_windows_drive_path": bool(re.search(r"[A-Za-z]:\\", readme)),
    }


def build_trace() -> dict:
    shipped = _shipped_reject()
    promoted, followup = _legacy_promote_and_followup()
    one_case = _one_case()
    states = [shipped, promoted, followup, one_case, *_safety(), *_rollback_states()]
    names = [state["name"] for state in states]
    if names != STATE_NAMES:
        raise RuntimeError(f"state coverage drift: {names}")
    if candidate_id({"normalize_case": True, "trim_whitespace": True}) != SOLVED_ID:
        raise RuntimeError("solved toy policy id changed")
    return {
        "benchmark": "examples/benchmark.json",
        "cases": 4,
        "consistency": _consistency(),
        "omitted_because_not_stable": [
            "duration_s",
            "latency_increase",
            "latency_s",
            "run_id",
        ],
        "package_version": __version__,
        "plateau_claim": {
            "claimed_active_id": SOLVED_ID,
            "claimed_in": "research/findings.md",
            "claimed_rounds": 10,
            "followup_round_promoted": followup["promoted"],
            "id_equals_solved_toy_policy": True,
            "json_files_with_that_id_excluding_this_trace": _json_files_with_token(SOLVED_ID),
        },
        "proves": "safety gate, min_gain compare, atomic promote, and rollback on a 4-case toy",
        "reasons_omit": ["latency_regression"],
        "schema": "toy-trace-v1",
        "states": states,
        "what_this_does_not_prove": "real agent improvement, a 10-round plateau, or any private benchmark score",
    }


def main() -> None:
    args = sys.argv[1:]
    trace = _dumps(build_trace())
    if args == ["--write", str(EVIDENCE)] or args == ["--write", "evidence/toy-trace.json"]:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(trace, encoding="utf-8")
        return
    if args == ["--check", str(EVIDENCE)] or args == ["--check", "evidence/toy-trace.json"]:
        current = EVIDENCE.read_text(encoding="utf-8") if EVIDENCE.exists() else ""
        if current != trace:
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                trace.splitlines(keepends=True),
                fromfile="evidence/toy-trace.json",
                tofile="recomputed",
            )
            sys.stderr.writelines(diff)
            raise SystemExit(1)
        return
    sys.stdout.write(trace)


if __name__ == "__main__":
    main()
