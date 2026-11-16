#!/usr/bin/env python3
"""把多次同设置复跑的 kind 级 L 判定摊成分布表（可复算，不手抄数字）。

## 为什么需要它

单跑只会给出一个 level。`prompt` 这个 kind 在 probe-01 是 L2，在 probe-01-rerun /
02 / 03 / 05 都是 L3 —— 于是「prompt 到底是 L2 还是 L3」在单跑视角下无法回答。
本脚本把 **同一模型 / 同一温度 / 同一 bench** 的 N 次复跑逐跑打分，输出
「哪个 kind 在几次里落到哪个 level」的分布，判据是计数而不是某一次的叙述。

## 判据（先验）

- 某 kind 的 level 在 N 次里全一致 → `STABLE`（可作为该 kind 在本 bench 上的稳定读数）。
- 出现 ≥2 种 level → `UNSTABLE`，并列出分布与各跑的 precision / 回归率，
  说明"该 kind 的 level 判定在低精度区不可复现，单跑不得当 kind 性质引用"。

输出：`PROMPT_VARIANCE.md` + `prompt_variance.json`（都在本目录）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "eval-meta"))

import eval_meta.trust as trust  # noqa: E402

KINDS = ("tool", "prompt", "middleware", "memory", "workflow", "subagent")


def _score(path: Path, basis: str) -> dict:
    rows = trust.load_verdicts(path)
    report = trust.score_history(rows, min_edits=trust.MIN_EDITS,
                                 regression_basis=basis)
    return {"rows": len(rows), "overall": report["verdict"],
            "kinds": report["kinds"]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="同设置复跑的 kind 级 L 分布")
    ap.add_argument("--ledgers", nargs="+", required=True,
                    help="同一模型/温度/bench 的账本路径（≥2 份才有分布意义）")
    ap.add_argument("--basis", default="edit", choices=("edit", "candidate"))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    missing = [p for p in args.ledgers if not Path(p).exists()]
    if missing:
        raise SystemExit("missing ledgers: " + ", ".join(missing))
    if len(args.ledgers) < 2:
        raise SystemExit("需要 ≥2 份账本才能算分布")

    out_dir = Path(args.out_dir) if args.out_dir else ROOT
    scored = {}
    for p in args.ledgers:
        path = Path(p)
        # 相对路径 `verdicts.jsonl` 的 parent.name 是空串，会产出无名行；
        # 统一按 resolve 后的父目录名做键，保证表行可辨认
        key = path.resolve().parent.name
        scored[key] = _score(path, args.basis)

    dist: dict[str, Counter] = {k: Counter() for k in KINDS}
    for key, rep in scored.items():
        for kind in KINDS:
            item = rep["kinds"].get(kind)
            dist[kind][item["level"] if item else "ABSENT"] += 1

    summary = {}
    for kind in KINDS:
        c = dist[kind]
        levels = sorted(c)
        summary[kind] = {
            "levels": levels,
            "counts": dict(c),
            "status": "STABLE" if len(levels) == 1 else "UNSTABLE",
            "n_runs": sum(c.values()),
        }

    lines = [
        "# PROMPT_VARIANCE — 同设置复跑的 kind 级 L 分布",
        "",
        f"- 复跑数：{len(scored)}；回归率口径：`{args.basis}`；"
        f"`MIN_EDITS={trust.MIN_EDITS}`",
        "- 判据（先验）：全一致 = `STABLE`；≥2 种 level = `UNSTABLE`（单跑不得当 kind 性质引用）",
        "",
        "## 逐跑读数",
        "",
        "| 账本 | 行 | overall | " + " | ".join(KINDS) + " |",
        "| --- | ---: | --- | " + " | ".join("---" for _ in KINDS) + " |",
    ]
    for key, rep in scored.items():
        cells = []
        for kind in KINDS:
            item = rep["kinds"].get(kind)
            cells.append(
                f"{item['level']} ({item['mean_precision']:.3f},"
                f"{item['regression_rate']:.3f})" if item else "—")
        lines.append(f"| {key} | {rep['rows']} | {rep['overall']} | "
                     + " | ".join(cells) + " |")

    lines += ["", "## 分布与判定", "",
              "| kind | 分布 | 判定 |", "| --- | --- | --- |"]
    for kind in KINDS:
        s = summary[kind]
        cells = ", ".join(f"{lvl}×{n}" for lvl, n in sorted(s["counts"].items()))
        lines.append(f"| {kind} | {cells} | **{s['status']}** |")

    unstable = [k for k in KINDS if summary[k]["status"] == "UNSTABLE"]
    lines += ["", "## 结论", ""]
    if unstable:
        lines.append(f"- `UNSTABLE`：{', '.join(unstable)} —— 这些 kind 的 level 在"
                     f"同设置复跑间不一致，任何单跑给出的 level 都不是该 kind 的稳定性质。")
    else:
        lines.append("- 六个 kind 的 level 在本复跑集内全部一致，可作为该 bench 上的稳定读数。")
    lines += ["- 机制 probe：不改任何阈值、不改论文数字。", ""]

    (out_dir / "PROMPT_VARIANCE.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "prompt_variance.json").write_text(
        json.dumps({"basis": args.basis, "min_edits": trust.MIN_EDITS,
                    "summary": summary,
                    "runs": {k: {"rows": v["rows"], "overall": v["overall"],
                                 "levels": {n: v["kinds"][n]["level"]
                                            for n in v["kinds"]}}
                             for k, v in scored.items()}},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote PROMPT_VARIANCE.md ({len(scored)} runs, unstable={unstable})")


if __name__ == "__main__":
    main()
