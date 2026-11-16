"""`campaigns/trust-probe-05-single-endpoint/variance_table.py` 的判定与假阳守卫。

为什么要这条：分布表的唯一产出是「STABLE / UNSTABLE」两个字。一个永远报
`UNSTABLE` 的表和一个永远报 `STABLE` 的表一样没有信息量，所以两条方向都要测：
**同一账本重复两次必须 STABLE**（不能因为复跑数>1 就喊不稳定），
**故意造出 level 不同的两份账本必须 UNSTABLE**。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "campaigns" / "trust-probe-05-single-endpoint" / "variance_table.py"


def _load():
    spec = importlib.util.spec_from_file_location("variance_table", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(kind: str, verdict: str, precision: float) -> dict:
    return {
        "run_id": "t", "candidate_id": f"{kind}-{verdict}-{precision}",
        "valid": True, "reasons": [],
        "prediction_precision": precision, "predicted_total": 1,
        "hit_total": 1 if precision else 0,
        "candidate_regression_rate": 0.0, "edit_regression_rate": 0.0,
        "edits": [{
            "edit_id": f"e-{kind}-{precision}", "kind": kind,
            "files": [f"harness/{kind}.yaml"], "verdict": verdict,
            "hits": [], "prediction_precision": precision,
            "predicted_fix": ["c09"], "predicted_regression": ["c05"],
            "attributed_regressions": [], "shared_unanticipated_regressions": [],
            "regression_attribution": "none",
            "unanticipated_regressions": [], "anticipated_regressions": [],
        }],
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def _high_precision(kind: str) -> list[dict]:
    """precision 1.0、零回归 → 该 kind 落 L1。"""
    return [_row(kind, "effective_fix", 1.0) for _ in range(6)]


def _low_precision(kind: str) -> list[dict]:
    """precision 0.0 且有回归 → 该 kind 落 L3（盲预测/高回归）。"""
    rows = [_row(kind, "regression", 0.0) for _ in range(5)]
    rows.append(_row(kind, "effective_fix", 1.0))
    return rows


def test_same_ledger_twice_stays_stable(tmp_path, capsys):
    """假阳守卫：同一份账本跑两次，level 必然一致 → 必须判 STABLE。"""
    vt = _load()
    p = tmp_path / "run-a" / "verdicts.jsonl"
    _write(p, [_row("tool", "effective_fix", 1.0) for _ in range(6)])
    p2 = tmp_path / "run-b" / "verdicts.jsonl"
    _write(p2, [_row("tool", "effective_fix", 1.0) for _ in range(6)])

    out = tmp_path / "out"
    out.mkdir()
    vt.main(["--ledgers", str(p), str(p2), "--out-dir", str(out)])
    summary = json.loads((out / "prompt_variance.json").read_text(encoding="utf-8"))["summary"]
    assert summary["tool"]["status"] == "STABLE", summary["tool"]
    assert summary["tool"]["counts"] == {"L1": 2}


def test_different_levels_across_runs_is_unstable(tmp_path):
    vt = _load()
    good = tmp_path / "r1" / "verdicts.jsonl"
    _write(good, _high_precision("prompt"))
    bad = tmp_path / "r2" / "verdicts.jsonl"
    _write(bad, _low_precision("prompt"))

    out = tmp_path / "out"
    out.mkdir()
    vt.main(["--ledgers", str(good), str(bad), "--out-dir", str(out)])
    summary = json.loads((out / "prompt_variance.json").read_text(encoding="utf-8"))["summary"]
    assert summary["prompt"]["status"] == "UNSTABLE", summary["prompt"]
    assert sum(summary["prompt"]["counts"].values()) == 2
    md = (out / "PROMPT_VARIANCE.md").read_text(encoding="utf-8")
    assert "UNSTABLE" in md and "prompt" in md


def test_single_ledger_is_refused(tmp_path):
    """一份账本没有「分布」可算——必须拒绝，而不是打印 STABLE 冒充已复算。"""
    vt = _load()
    p = tmp_path / "one" / "verdicts.jsonl"
    _write(p, _high_precision("tool"))
    try:
        vt.main(["--ledgers", str(p), "--out-dir", str(tmp_path)])
    except SystemExit as exc:
        assert "≥2" in str(exc)
    else:  # pragma: no cover - 走到这里说明守卫失效
        raise AssertionError("单账本未被拒绝")
    assert not (tmp_path / "prompt_variance.json").exists()


def test_missing_ledger_fails_loud(tmp_path):
    vt = _load()
    try:
        vt.main(["--ledgers", str(tmp_path / "nope.jsonl"), str(tmp_path / "nope2.jsonl"),
                 "--out-dir", str(tmp_path)])
    except SystemExit as exc:
        assert "missing ledgers" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("缺账本未被拒绝")


def test_script_reaches_repo_eval_meta():
    """路径必须真的指向本仓 eval-meta（曾写成 parents[3] 直接 ModuleNotFound）。"""
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'ROOT.parents[2] / "eval-meta"' in text
    assert sys.path is not None
