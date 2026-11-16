#!/usr/bin/env python3
"""P4 阈值判别力扫描 v2：修掉 v1 的「翻转」定义错误，并新增回归率口径轴。

## v1 的缺陷（本轮实测发现，2026-11-16）

v1（`calibrate.py`）把 `changed_vs_baseline`（与基线 **RBR=0.30** 的差）当成「翻转」。
这混淆了两件事：一个阈值「看起来与基线不同」不等于「它跨过了一个数据边界」。
后果是把真账本判成 `NO_DISCRIMINATION`——因为 0.0 和 1.0 与 0.30 不同、而 0.1/0.3/0.5
三者彼此相同，看起来只剩两个端点会动。正确的判据是**相邻格点之间**是否变：
真正的数据边界才落在那里。

## v2 的两条轴

1. **回归率口径**：`edit`（逐编辑，shared blame 会压平）vs `candidate`（逐候选）。
2. **阈值位置**：整个网格逐点走，记录 level 向量，并算出**稳定区间**
   （相邻两个数据边界之间的开区间）——阈值在这个区间里怎么挪都不改判决。

## 判据（说明「判别力」到底靠什么算）

- `distinct_vectors`：网格上出现过多少种不同的 level 向量。1 种 = 该阈值在这份账本上
  完全没有判别力；≥2 种 = 存在判别力。
- `boundaries`：相邻格点之间 level 向量发生变化的**阈值位置**，即真实数据边界。
- `stable_interval_of_original`：原值落在哪个开区间里，以及到两端的余量。
  原值贴着边界 = 脆；落在宽区间中部 = 稳。这是「阈值有没有过拟合」的可复算答案。

输出：`calibration_basis.json` + stdout markdown 表。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "eval-meta"))

import eval_meta.trust as trust  # noqa: E402

# 三份真账本（同一 12 例 bench，不同模型/温度）
LEDGERS = (
    ROOT / "verdicts.jsonl",
    ROOT.parent / "trust-probe-02-rerun-qwenflash" / "verdicts.jsonl",
    ROOT.parent / "trust-probe-03-rerun-temp05" / "verdicts.jsonl",
)

# 网格比 v1 更密：v1 的 0.1/0.3/0.5 三点太稀，恰好跨不过 0.045 这个真边界
GRID = {
    # 网格必须跨过「每类样本量」本身，否则 MIN_EDITS 会因全格点都在样本量之下
    # 而显示为 0 判别力（那是网格没铺到位，不是阈值没有边界）
    "MIN_EDITS": [1, 3, 5, 6, 8, 10, 11, 20, 31, 32, 33, 50],
    "REGRESSION_BLOCK_RATE": [0.0, 0.03, 0.045, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.999, 1.0],
    "PRECISION_TRUST_FLOOR": [0.0, 0.1, 0.2, 0.35, 0.5, 0.6, 0.75, 0.9, 0.95],
    "PRECISION_BLIND_FLOOR": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5],
    "REGRESSION_TRUST_CEIL": [0.0, 0.03, 0.045, 0.05, 0.1, 0.3, 0.5, 1.0],
}
BASES = ("edit", "candidate")


def _levels(rows, basis):
    report = trust.score_history(rows, min_edits=trust.MIN_EDITS,
                                regression_basis=basis)
    return (report["verdict"],
            tuple(sorted((k, v["level"]) for k, v in report["kinds"].items())))


def sweep_threshold(name, grid, rows, basis):
    """走完整个网格，按**相邻格点**变化定边界，返回可复算的读数。"""
    original = getattr(trust, name)
    seen = []
    for value in grid:
        setattr(trust, name, value)
        try:
            verdict, levels = _levels(rows, basis)
        finally:
            setattr(trust, name, original)
        seen.append((value, verdict, levels))

    distinct = sorted({levels for _, _, levels in seen}, key=str)
    boundaries = [seen[i][0] for i in range(1, len(seen))
                  if seen[i][2] != seen[i - 1][2]]
    # 原值落在哪个开区间：端点取「边界值本身」也算落在该段（阈值取等号时行为已知）
    lower = max([b for b in boundaries if b < original], default=None)
    upper = min([b for b in boundaries if b > original], default=None)
    return {
        "original": original,
        "grid": grid,
        "distinct_vectors": len(distinct),
        "discriminating": len(distinct) > 1,
        "boundaries": boundaries,
        "original_interval": {"lower_boundary": lower, "upper_boundary": upper,
                              "unbounded_low": lower is None,
                              "unbounded_high": upper is None},
        "at_original": dict(seen[[v for v, _, _ in seen].index(original)][2]),
        "points": [{"value": v, "verdict": vd, "levels": dict(lv)} for v, vd, lv in seen],
    }


def main() -> None:
    ledgers = [p for p in LEDGERS if p.exists()]
    if not ledgers:
        raise SystemExit("no ledgers found")
    rows = []
    for p in ledgers:
        rows += trust.load_verdicts(p)
    if not rows:
        raise SystemExit("ledgers empty")

    print(f"# ledgers: {len(ledgers)}  rows: {len(rows)}\n")
    out = {"ledgers": [str(p.relative_to(ROOT.parents[2])) for p in ledgers],
           "rows": len(rows), "sweeps": {}}

    for basis in BASES:
        base_verdict, base_levels = _levels(rows, basis)
        print(f"## 回归率口径 = {basis}")
        print(f"   基线判决 {base_verdict}: "
              + " ".join(f"{k}={v}" for k, v in base_levels))
        block = {}
        for name, grid in GRID.items():
            res = sweep_threshold(name, grid, rows, basis)
            block[name] = res
            mark = "YES" if res["discriminating"] else "NO "
            print(f"  {name:<22} distinct={res['distinct_vectors']:>2} "
                  f"discriminating={mark} boundaries={res['boundaries']} "
                  f"original={res['original']} in "
                  f"({res['original_interval']['lower_boundary']}, "
                  f"{res['original_interval']['upper_boundary']})")
        out["sweeps"][basis] = {"baseline": {"verdict": base_verdict,
                                             "levels": dict(base_levels)},
                                "thresholds": block}
        print()

    (ROOT / "calibration_basis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8")
    print("wrote calibration_basis.json")


if __name__ == "__main__":
    main()
