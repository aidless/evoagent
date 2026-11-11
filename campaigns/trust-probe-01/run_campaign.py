#!/usr/bin/env python3
"""trust-probe-01 的 12 轮编排器：detached + checkpoint，支持 --resume 断点续跑。

用法（在 campaigns/trust-probe-01 目录下）：
    {python} run_campaign.py --rounds 12
    {python} run_campaign.py --rounds 12 --resume

契约（core.py:199 evolve）：每轮一次 evolve()，即 1 次 Magpie propose +
(baseline + 3 候选) × 12 用例的确定性评测 + per-edit 对账落账。
`min_gain: 2.0`（evo.json）保证永不晋升，12 轮 baseline/failures 完全固定。

产物：
- verdicts.jsonl     真账本（从 .evo/verdicts.jsonl 拷出，.evo/ 被 gitignore）
- checkpoint.json    断点续跑状态 + 每轮摘要
- campaign_report.json  终态（墙钟、轮数、失败轮、按 kind 计数）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "src"))

from evoagent.cli import init  # noqa: E402
from evoagent.core import evolve  # noqa: E402

VERDICTS = ROOT / "verdicts.jsonl"
CHECKPOINT = ROOT / "checkpoint.json"
REPORT = ROOT / "campaign_report.json"


def _load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8-sig"))
    return {"completed_rounds": [], "failed_rounds": [], "rounds": []}


def _save(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _kind_counts() -> dict:
    counts: dict[str, int] = {}
    if VERDICTS.exists():
        for line in VERDICTS.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for edit in row.get("edits") or ():
                kind = str(edit.get("kind") or "unknown")
                counts[kind] = counts.get(kind, 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    init(ROOT)
    state = _load_checkpoint()
    done = set(state["completed_rounds"])
    started_wall = time.time()

    for rnd in range(args.rounds):
        if args.resume and rnd in done:
            print(f"[campaign] round {rnd} already completed, skip", file=sys.stderr)
            continue
        print(f"[campaign] round {rnd} start", file=sys.stderr, flush=True)
        round_started = time.time()
        os.environ["EVO_ROUND"] = str(rnd)
        try:
            report = evolve(ROOT)
            n_candidates = len(report.get("candidates") or [])
            run_id = report.get("run_id", "")
            promoted = bool(report.get("promoted"))
        except Exception as exc:  # noqa: BLE001 — 失败轮必须落痕，不允许悄悄跳过
            state["failed_rounds"].append(rnd)
            state["rounds"].append({"round": rnd, "error": f"{type(exc).__name__}: {exc}"})
            _save(CHECKPOINT, state)
            print(f"[campaign] round {rnd} FAILED: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
            time.sleep(1.05)
            continue
        source = ROOT / ".evo" / "verdicts.jsonl"
        if source.exists():
            shutil.copy2(source, VERDICTS)
        entry = {"round": rnd, "run_id": run_id, "candidates": n_candidates,
                 "promoted": promoted,
                 "duration_s": round(time.time() - round_started, 2)}
        state["rounds"].append(entry)
        if n_candidates == 0:
            state["failed_rounds"].append(rnd)
            print(f"[campaign] round {rnd} empty proposals -> failed_rounds",
                  file=sys.stderr, flush=True)
        else:
            state["completed_rounds"].append(rnd)
            print(f"[campaign] round {rnd} ok candidates={n_candidates} "
                  f"run_id={run_id} promoted={promoted}", file=sys.stderr, flush=True)
        _save(CHECKPOINT, state)
        # run_id 是秒级精度（core.py:220），保证每轮落不同的 runs/*.json
        time.sleep(1.05)

    counts = _kind_counts()
    summary = {
        "prereg": "PREREG.md",
        "rounds_total": args.rounds,
        "completed_rounds": state["completed_rounds"],
        "failed_rounds": state["failed_rounds"],
        "verdicts_rows": sum(1 for _ in VERDICTS.open(encoding="utf-8")) if VERDICTS.exists() else 0,
        "kind_counts": counts,
        "wall_clock_s": round(time.time() - started_wall, 2),
        "resumed": bool(args.resume),
    }
    _save(REPORT, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
