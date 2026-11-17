"""判据 B 成本分层：用 core 当时真测的 latency 回填旧账本，按三分位切层重切 L 判定。

为什么需要回填：v3 的 5 份账本跑在 f982464（cost/latency 落盘）之前，账本行没有
evaluation_* 字段；但每次 evolve 的 .evo/runs/*.json 里 core.evaluate 已把每例
latency_s 真测落盘。按 (run_id, candidate_id) join 是同一份原始测量的搬运，不是编造。

跑前声明的判据（先于看结果固定）：
- H0：prompt 的 L2↔L3 抖动可由评测成本（这里只有 latency 是真值）分层解释。
- 支持判据：low/mid/high 三层的 prompt 样本各 ≥ MIN_EDITS，且 level 随层单调变化
  （如 low=L2, high=L3）或某层单独不同且其余两层一致。
- 否决判据：任一层样本 <MIN_EDITS（功效不足），或三层 level 全同 / 无结构。
- 诚实边界：latency 是本地 subprocess 墙钟，非 token 成本；cost 恒 0 是 bench 真相。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "eval-meta"))

import eval_meta.trust as trust  # noqa: E402

KINDS = ("tool", "prompt", "middleware", "memory", "workflow", "subagent")


def load_true_latency(runs_dir: Path) -> dict[tuple[str, str], float]:
    """从 .evo/runs/*.json 取 core 真测的每候选总 latency（每例 latency_s 求和）。"""
    out: dict[tuple[str, str], float] = {}
    for path in sorted(runs_dir.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8-sig"))
        run_id = report["run_id"]
        for cand in report["candidates"]:
            outcomes = (cand.get("evaluation") or {}).get("outcomes") or ()
            total = round(sum(float(o.get("latency_s", 0.0)) for o in outcomes), 6)
            out[(run_id, cand["id"])] = total
    return out


def backfill(ledger: list[dict], latency: dict[tuple[str, str], float]) -> list[dict]:
    """给账本行加 evaluation_latency_s；join 不到则填 None（不编造）。"""
    rows = []
    for r in ledger:
        row = dict(r)
        key = (r.get("run_id"), r.get("candidate_id"))
        row["evaluation_latency_s"] = latency.get(key)
        rows.append(row)
    return rows


def assign_layers(rows: list[dict], n_layers: int = 3) -> dict[str, list[dict]]:
    """按候选 latency 全局三分位切层，低/中/高。缺 latency 的行不进任何层。"""
    with_lat = [r for r in rows if r.get("evaluation_latency_s") is not None]
    ordered = sorted(with_lat, key=lambda r: r["evaluation_latency_s"])
    layers: dict[str, list[dict]] = {f"L{i+1}": [] for i in range(n_layers)}
    for i, r in enumerate(ordered):
        bucket = min(n_layers - 1, i * n_layers // len(ordered))
        layers[f"L{bucket+1}"].append(r)
    return layers


def layer_report(rows: list[dict], *, basis: str = "edit") -> dict:
    """对每层跑 trust.score_history，返回各层各 kind 的 level / precision / 样本数。"""
    layers = assign_layers(rows)
    result: dict[str, dict] = {}
    for name, layer_rows in layers.items():
        report = trust.score_history(layer_rows, min_edits=trust.MIN_EDITS,
                                     regression_basis=basis)
        result[name] = {
            "rows": len(layer_rows),
            "latency_range_s": [
                round(layer_rows[0]["evaluation_latency_s"], 6),
                round(layer_rows[-1]["evaluation_latency_s"], 6),
            ] if layer_rows else None,
            "kinds": {k: {
                "level": report["kinds"][k]["level"],
                "mean_precision": report["kinds"][k].get("mean_precision"),
                "n_edits": report["kinds"][k].get("n_edits"),
                "reasons": report["kinds"][k].get("reasons", []),
            } for k in KINDS if k in report["kinds"]},
        }
    return result


def judge(rep: dict, kind: str = "prompt") -> dict:
    """按跑前声明的判据机械判决，不看数值细节做解释。"""
    levels = {layer: rep[layer]["kinds"].get(kind, {}).get("level", "MISSING")
              for layer in sorted(rep)}
    sizes = {layer: rep[layer]["kinds"].get(kind, {}).get("n_edits", 0)
             for layer in sorted(rep)}
    insufficient = [l for l, n in sizes.items() if n < trust.MIN_EDITS]
    distinct = set(levels.values())
    if insufficient:
        verdict = "NO_POWER"
        reason = f"layers below MIN_EDITS={trust.MIN_EDITS}: {insufficient}"
    elif distinct == {"L3"} or distinct == {"L2"}:
        verdict = "REJECT_NO_STRUCTURE"
        reason = "all layers share one level -> cost stratification does not explain jitter"
    elif len(distinct) >= 2:
        seq = [levels[l] for l in sorted(levels)]
        monotonic = (seq == sorted(seq, reverse=True) or seq == sorted(seq))
        verdict = "SUPPORT" if monotonic else "REJECT_NO_STRUCTURE"
        reason = ("level varies monotonically across cost layers" if monotonic
                  else "level varies but not monotonically across cost layers")
    else:
        verdict = "REJECT_NO_STRUCTURE"
        reason = f"unexpected level set: {sorted(distinct)}"
    return {"verdict": verdict, "reason": reason, "levels": levels,
            "sizes": sizes, "kind": kind}


def main() -> None:
    ledgers = [
        Path(__file__).resolve().parents[1] / d / "verdicts.jsonl"
        for d in ("trust-probe-01-rerun-c4badd0", "trust-probe-05-single-endpoint",
                  "trust-probe-05b-single-endpoint", "trust-probe-05c-single-endpoint",
                  "trust-probe-04b-attribution-kinds")
    ]
    rows: list[dict] = []
    missing_join = 0
    for lp in ledgers:
        ledger = [json.loads(l) for l in lp.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        truth = load_true_latency(lp.parent / ".evo" / "runs")
        back = backfill(ledger, truth)
        missing_join += sum(1 for r in back if r["evaluation_latency_s"] is None)
        rows.extend(back)
    rep = layer_report(rows)
    result = {"rows_total": len(rows), "missing_latency_join": missing_join,
              "layers": rep, "judgment": judge(rep, "prompt"),
              "basis": "real core-measured latency_s from runs/*.json; cost=0 is bench truth"}
    out = Path(__file__).resolve().parent / "cost_layer_reprobe.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rows={len(rows)} missing_join={missing_join} verdict={result['judgment']['verdict']}")
    for layer in sorted(rep):
        p = rep[layer]["kinds"].get("prompt", {})
        print(f"  {layer}: prompt level={p.get('level')} n={p.get('n_edits')} "
              f"mean_precision={p.get('mean_precision')}")
    print(f"  written: {out}")


if __name__ == "__main__":
    main()
