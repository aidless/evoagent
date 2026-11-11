#!/usr/bin/env python3
"""P4 阈值判别力扫描（可复算证据，不是肉眼判断）。

对每一个阈值做「原值 vs 跨观测值」的网格扫描，问一个只有数据能回答的问题：
把这条阈值挪到别处，P4 的 level 向量会不会变？不会变 = 这条阈值在这份账本上
没有判别力（NO_DISCRIMINATION），按 PREREG 不许事后调它去凑结论。

输出：calibration_sweep.json + stdout 的 markdown 表。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "eval-meta"))

import eval_meta.trust as trust  # noqa: E402

THRESHOLDS = {
    "MIN_EDITS": [1, 3, 5, 6, 8, 10, 11, 20],
    "REGRESSION_BLOCK_RATE": [0.0, 0.1, 0.3, 0.5, 0.9, 1.0],
    "PRECISION_TRUST_FLOOR": [0.2, 0.35, 0.5, 0.6, 0.75, 0.9],
    "PRECISION_BLIND_FLOOR": [0.0, 0.1, 0.2, 0.3, 0.5],
    "REGRESSION_TRUST_CEIL": [0.0, 0.05, 0.1, 0.5, 0.9, 1.0],
}


def _levels(rows):
    # 注意：score_history 的 min_edits 默认值在 def 时绑定（int = MIN_EDITS），
    # 改模块全局不会影响它——扫描必须显式把值传进去，否则这一格是空转的装饰。
    report = trust.score_history(rows, min_edits=trust.MIN_EDITS)
    return (report["verdict"],
            tuple(sorted((k, v["level"]) for k, v in report["kinds"].items())))


def main() -> None:
    ledger = ROOT / "verdicts.jsonl"
    rows = trust.load_verdicts(ledger)
    if not rows:
        raise SystemExit(f"empty or missing ledger: {ledger}")
    base_verdict, base_levels = _levels(rows)
    print(f"# ledger rows: {len(rows)}  baseline verdict: {base_verdict}\n")

    out = {"ledger": ledger.name, "rows": len(rows), "baseline": {
        "verdict": base_verdict, "levels": dict(base_levels)}, "sweeps": {}}

    for name, values in THRESHOLDS.items():
        original = getattr(trust, name)
        records = []
        for value in values:
            setattr(trust, name, value)
            verdict, levels = _levels(rows)
            records.append({
                "value": value,
                "verdict": verdict,
                "levels": dict(levels),
                "changed_vs_baseline": (verdict, levels) != (base_verdict, base_levels),
            })
        setattr(trust, name, original)
        flips = [r for r in records if r["changed_vs_baseline"]]
        out["sweeps"][name] = {"original": original, "grid": values,
                              "records": records,
                              "flip_values": [r["value"] for r in flips],
                              "discriminating": bool(flips) and any(
                                  v != original for v in [r["value"] for r in flips])}
        print(f"## {name} (original={original})")
        for r in records:
            mark = "  ← flip" if r["changed_vs_baseline"] else ""
            print(f"  {r['value']:>6} → {r['verdict']:>12}{mark}")
        print()

    (ROOT / "calibration_sweep.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote calibration_sweep.json")


if __name__ == "__main__":
    main()
