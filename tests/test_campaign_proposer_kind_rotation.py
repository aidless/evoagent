"""campaigns/*/proposer.py 的 kind 轮转是否真的覆盖 6 类（假阳守卫 + 反证）。

背景（2026-11-16 实测）：`trust-probe-04-attribution` 的 1-edit 变体里 kind 写成
`KINDS[(round_no * 6 + j) % len(KINDS)]`。因为 `round_no * 6` 恒被 6 整除，这个
表达式等价于 `KINDS[j % 6]`，而 j 只取 0/1/2 —— 于是 12 轮 × 3 候选 = 36 笔只落到
tool/prompt/middleware 三类（实测 `verdicts.jsonl` kind 计数正是 {tool:12,
prompt:12, middleware:12}），memory/workflow/subagent 三类的 1-edit 证据为零。

本测试不读账本（账本会被重跑）而是直接驱动 proposer 的轮转函数，要求 12 轮 × 3
候选完整覆盖 6 类且每类恰好 6 笔；并配一条反证断言：把旧公式塞回去必须红。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROPOSER_PATH = (REPO / "campaigns" / "trust-probe-04-attribution" / "proposer.py")


def _load_proposer():
    spec = importlib.util.spec_from_file_location("tp04_proposer", PROPOSER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def proposer():
    return _load_proposer()


def test_kind_for_covers_all_six_kinds_over_twelve_rounds(proposer):
    """12 轮 × 3 候选 = 36 笔，6 类各 6 笔（这是 PREREG 承诺的证据形态）。"""
    counts: dict[str, int] = {}
    for round_no in range(12):
        for j in range(3):
            kind = proposer.kind_for(round_no, j)
            counts[kind] = counts.get(kind, 0) + 1
    assert set(counts) == set(proposer.KINDS), (
        f"kind 未覆盖全部 6 类，实际 {sorted(counts)}")
    assert counts == {k: 6 for k in proposer.KINDS}, f"计数不均衡: {counts}"
    assert sum(counts.values()) == 36


def test_kind_for_is_stable_and_distinct_within_a_round(proposer):
    """同一轮内 3 个候选必须是不同 kind；同一 (round, j) 重算必须一致（可复算）。"""
    for round_no in range(12):
        kinds = [proposer.kind_for(round_no, j) for j in range(3)]
        assert len(set(kinds)) == 3, f"round={round_no} 同轮 kind 重复: {kinds}"
        assert kinds == [proposer.kind_for(round_no, j) for j in range(3)]


def test_old_rotation_formula_would_fail_this_assertion(proposer):
    """反证（非空性守卫）：旧的 `(round_no * 6 + j) % 6` 只有 3 类 → 断言必红。

    这条不是测代码，是测本组断言本身能红。若哪天有人把断言放宽到「≥3 类」，
    这条会继续通过而缺陷复发，所以这里显式把旧公式算出来对照。
    """
    old = proposer.KINDS[(0 * 6 + 1) % len(proposer.KINDS)]
    old_counts: dict[str, int] = {}
    for round_no in range(12):
        for j in range(3):
            kind = proposer.KINDS[(round_no * 6 + j) % len(proposer.KINDS)]
            old_counts[kind] = old_counts.get(kind, 0) + 1
    assert set(old_counts) == {"tool", "prompt", "middleware"}, old_counts
    assert len(old_counts) == 3
    # 与主断言对照：旧公式确实过不了 `set(counts) == set(KINDS)`
    assert set(old_counts) != set(proposer.KINDS)
    assert old in {"tool", "prompt", "middleware"}


def test_proposer_emits_one_edit_per_candidate(proposer, tmp_path, monkeypatch):
    """1-edit 变体的硬约束：任何候选都只能有 1 笔 edit（否则归因退化为 shared）。"""
    monkeypatch.chdir(PROPOSER_PATH.parent)
    raw = [
        {"trim_whitespace": True, "collapse_spaces": False, "strip_punct": False,
         "normalize_case": False, "dedupe_words": False, "reverse_words": False,
         "edits": [
             {"predicted_fix": ["c09"], "predicted_regression": ["c05"],
              "rationale": "首尾空白"},
             {"predicted_fix": ["c11"], "predicted_regression": [],
              "rationale": "多余的第二笔，必须被裁掉"},
         ]},
    ]
    case_ids = {f"c{i:02d}" for i in range(1, 13)}
    out = proposer._sanitize(raw, case_ids, round_no=3)
    assert len(out) == 1
    edits = out[0]["change_manifest"]["edits"]
    assert len(edits) == 1
    assert edits[0]["predicted_fix"] == ["c09"]
    assert edits[0]["edit_id"] == "r03c0e0"
    assert edits[0]["kind"] == proposer.kind_for(3, 0)


def test_sanitize_drops_unknown_task_ids(proposer, monkeypatch):
    """幻觉 id 必须拦在账本之外（沿用 probe-01 的真实性边界）。"""
    monkeypatch.chdir(PROPOSER_PATH.parent)
    raw = [
        {"trim_whitespace": True, "collapse_spaces": False, "strip_punct": False,
         "normalize_case": False, "dedupe_words": False, "reverse_words": False,
         "edits": [{"predicted_fix": ["c99"], "predicted_regression": [],
                    "rationale": "幻觉 id"}]},
    ]
    out = proposer._sanitize(raw, {f"c{i:02d}" for i in range(1, 13)}, round_no=0)
    assert out == []


def test_benchmark_ids_are_the_twelve_expected(proposer):
    """prompt 里写死的 c01..c08 通过 / c09..c12 用例必须与 bench 一致。"""
    monkeypatch_cwd = PROPOSER_PATH.parent
    cases = json.loads((monkeypatch_cwd / "benchmark.json")
                       .read_text(encoding="utf-8-sig"))["cases"]
    ids = [str(c["id"]) for c in cases]
    assert ids == [f"c{i:02d}" for i in range(1, 13)]
