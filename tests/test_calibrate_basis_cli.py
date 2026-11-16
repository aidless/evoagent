"""`campaigns/trust-probe-01/calibrate_basis.py` 的 CLI 契约：`--ledgers` / `--out`。

为什么要这条测试：v3 合并分析要把**新账本**（probe-01-rerun / probe-04b / probe-05）
一起喂进稠密网格，而原脚本把三份账本路径写死在 `LEDGERS` 常量里、输出固定写
`calibration_basis.json` 覆盖 v2 产物。写死路径的仪器一旦被复用就会静默读旧账本
（第 37 条「语料源错」型假阳），所以这里把「换账本/换输出路径真的生效」变成断言。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "campaigns" / "trust-probe-01" / "calibrate_basis.py"
PYTHON = sys.executable


def _row(edit_kind: str, verdict: str, cand_rate: float, edit_rate: float,
         attributed: list[str] | None = None) -> dict:
    return {
        "run_id": "t", "candidate_id": f"c-{edit_kind}-{verdict}",
        "valid": True, "reasons": [],
        "prediction_precision": 1.0, "predicted_total": 1, "hit_total": 1,
        "candidate_regression_rate": cand_rate,
        "edit_regression_rate": edit_rate,
        "edits": [{
            "edit_id": f"e-{edit_kind}", "kind": edit_kind,
            "files": [f"harness/{edit_kind}.yaml"], "verdict": verdict,
            "hits": [], "prediction_precision": 1.0,
            "predicted_fix": ["c09"], "predicted_regression": ["c05"],
            "attributed_regressions": attributed or [],
            "shared_unanticipated_regressions": [],
            "regression_attribution": "attributed" if attributed else "none",
            "unanticipated_regressions": attributed or [],
            "anticipated_regressions": [],
        }],
    }


def _write_ledger(path: Path) -> None:
    rows = [
        _row("tool", "effective_fix", 0.0, 0.0),
        _row("tool", "no_effect", 0.0, 0.0),
        _row("prompt", "regression", 1.0, 1.0, attributed=["c05"]),
        _row("prompt", "regression", 1.0, 1.0, attributed=["c07"]),
        _row("middleware", "effective_fix", 0.0, 0.0),
        _row("memory", "regression", 1.0, 1.0, attributed=["c05"]),
    ]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def test_cli_honors_explicit_ledgers_and_out(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger)
    out = tmp_path / "sweep.json"

    proc = subprocess.run(
        [PYTHON, str(SCRIPT), "--ledgers", str(ledger), "--out", str(out)],
        capture_output=True, text=True, cwd=str(SCRIPT.parent), timeout=300)

    assert proc.returncode == 0, proc.stderr
    assert out.exists(), "未按 --out 写产物"
    data = json.loads(out.read_text(encoding="utf-8"))
    # 账本来源必须回显成传入的那一份，而不是写死的三份默认值
    assert len(data["ledgers"]) == 1
    assert data["ledgers"][0].endswith("ledger.jsonl"), data["ledgers"]
    # 必须是相对路径：绝对个人路径会被 publish gate 拒（见 tools/check_publish.py）
    assert not Path(data["ledgers"][0]).is_absolute(), data["ledgers"]
    assert data["rows"] == 6
    assert set(data["sweeps"]) == {"edit", "candidate"}
    for basis in ("edit", "candidate"):
        block = data["sweeps"][basis]
        assert set(block["thresholds"]) == {
            "MIN_EDITS", "REGRESSION_BLOCK_RATE", "PRECISION_TRUST_FLOOR",
            "PRECISION_BLIND_FLOOR", "REGRESSION_TRUST_CEIL",
        }
        # 网格必须原样落盘，便于事后复算边界
        for name, res in block["thresholds"].items():
            assert res["grid"], f"{basis}/{name} 网格为空"
            assert res["original"] is not None
    # 默认产物不能被这次显式 --out 调用写坏
    default = SCRIPT.parent / "calibration_basis.json"
    assert default.exists()
    assert json.loads(default.read_text(encoding="utf-8"))["rows"] != 6


def test_default_ledgers_are_the_three_probes():
    """默认口径必须仍是 probe-01/02/03（v2 结论的可复算基线），不许悄悄改。"""
    text = SCRIPT.read_text(encoding="utf-8")
    for name in ('"verdicts.jsonl"',
                 'trust-probe-02-rerun-qwenflash',
                 'trust-probe-03-rerun-temp05'):
        assert name in text, f"默认账本集合里缺 {name}"


def test_unknown_ledger_path_is_rejected(tmp_path):
    """缺账本要 fail-loud，不能退化成空网格然后写出「无判别力」的报告。"""
    proc = subprocess.run(
        [PYTHON, str(SCRIPT), "--ledgers", str(tmp_path / "nope.jsonl"),
         "--out", str(tmp_path / "out.json")],
        capture_output=True, text=True, cwd=str(SCRIPT.parent), timeout=300)
    assert proc.returncode != 0
    assert "no ledgers found" in (proc.stdout + proc.stderr)
    assert not (tmp_path / "out.json").exists()


# ---------------------------------------------------------------- MIN_EDITS 网格
# v3 合并 5 份账本后每类 50 笔，而 GRID["MIN_EDITS"] 只铺到 50 —— 于是所有格点都在
# 样本量之下，扫描报 distinct=1「无判别力」。这不是阈值没有边界，是**网格没跨过
# 样本量本身**（v2 已踩过一次，当时每类 32 笔、网格止于 20）。修法是让网格随数据
# 自适应：把「每类最大笔数」和「它 +1」都铺进网格。

def _load_script_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("calibrate_basis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows_with_n_per_kind(n: int, kinds=("tool", "prompt")) -> list[dict]:
    rows = []
    for kind in kinds:
        for i in range(n):
            rows.append(_row(kind, "effective_fix", 0.0, 0.0, attributed=[]))
            rows[-1]["candidate_id"] = f"{kind}-{i}"
    return rows


def test_min_edits_grid_crosses_per_kind_sample_size():
    cb = _load_script_module()
    grid = cb.min_edits_grid(_rows_with_n_per_kind(20))
    assert 20 in grid and 21 in grid, grid
    assert grid == sorted(grid)
    # 旧格点必须保留，v2 的边界 [33] 仍可复算
    for legacy in (5, 11, 33):
        assert legacy in grid


def test_min_edits_grid_never_empty_without_rows():
    cb = _load_script_module()
    assert cb.min_edits_grid([]) == sorted(cb.GRID["MIN_EDITS"])
