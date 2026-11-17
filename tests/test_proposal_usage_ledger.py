"""LLM token 用量落盘链路测试。

判据（跑前声明，AGENTS.local 第15条 / 用户 m02175「全做」）：
- 真实用量来自 Magpie 响应的 usage（已实测 free 模型带 usage）。
- token 数 ≠ 钱：字段一律叫 *_tokens，绝不叫 cost；不把 token 比例写成成本比例。
- 一次 propose 调用产出多个候选，usage 是批次级的：每个候选都带同一份 usage 并
  标注 batch_size，禁止摊薄成单候选成本（摊薄=编造）。
- 旧账本（无 usage 字段）兼容：落 None，不编造。
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from evoagent.verdict_history import append_verdicts, read_verdicts  # noqa: E402

MAGPIE_PAYLOAD = {
    "choices": [{"message": {"content": "[]"}}],
    "usage": {
        "prompt_tokens": 1128,
        "completion_tokens": 8,
        "total_tokens": 1136,
        "prompt_tokens_details": {"cached_tokens": 768, "cache_write_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 8},
    },
}


def _usage_mod():
    from evoagent import llm_usage
    return llm_usage


def _record(candidate: dict) -> dict:
    return {
        "id": "cand-u", "safe": True, "candidate": candidate,
        "change_verdict": {
            "valid": True,
            "edits": {"e1": {"edit_id": "e1", "kind": "tool", "files": ["x.yaml"],
                             "verdict": "no_effect", "hits": [],
                             "prediction_precision": 1.0,
                             "predicted_fix": ["c01"], "predicted_regression": []}},
            "campaign": {"prediction_precision": 1.0, "predicted_total": 1, "hit_total": 1},
        },
    }


class UsageExtractionTests(unittest.TestCase):
    def test_extract_from_magpie_payload(self):
        m = _usage_mod()
        u = m.extract_usage(MAGPIE_PAYLOAD)
        self.assertEqual(u["prompt_tokens"], 1128)
        self.assertEqual(u["completion_tokens"], 8)
        self.assertEqual(u["total_tokens"], 1136)
        self.assertEqual(u["cached_tokens"], 768)
        self.assertEqual(u["reasoning_tokens"], 8)

    def test_extract_missing_usage_is_none(self):
        m = _usage_mod()
        self.assertIsNone(m.extract_usage({"choices": []}))

    def test_attach_batch_usage_to_all_candidates(self):
        m = _usage_mod()
        usage = m.extract_usage(MAGPIE_PAYLOAD)
        out = m.attach_usage([{"a": 1}, {"a": 2}, {"a": 3}], usage)
        for c in out:
            self.assertEqual(c["proposal_usage"]["prompt_tokens"], 1128)
            self.assertEqual(c["proposal_usage"]["batch_size"], 3)
        self.assertEqual(out[0]["a"], 1)  # 原候选内容不变


class UsageLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / ".evo"
        self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_proposal_tokens_persisted(self):
        cand = {"proposal_usage": {"prompt_tokens": 1128, "completion_tokens": 8,
                                   "total_tokens": 1136, "cached_tokens": 768,
                                   "reasoning_tokens": 8, "batch_size": 3,
                                   "model": "free/model"}}
        append_verdicts(self.state, "run-u", (_record(cand),))
        row = read_verdicts(self.state.parent)[0]
        self.assertEqual(row["proposal_prompt_tokens"], 1128)
        self.assertEqual(row["proposal_completion_tokens"], 8)
        self.assertEqual(row["proposal_total_tokens"], 1136)
        self.assertEqual(row["proposal_cached_tokens"], 768)
        self.assertEqual(row["proposal_reasoning_tokens"], 8)
        self.assertEqual(row["proposal_batch_size"], 3)
        self.assertEqual(row["proposal_model"], "free/model")

    def test_no_usage_backward_compat_none(self):
        append_verdicts(self.state, "run-u", (_record({"a": 1}),))
        row = read_verdicts(self.state.parent)[0]
        for key in ("proposal_prompt_tokens", "proposal_completion_tokens",
                    "proposal_total_tokens", "proposal_cached_tokens",
                    "proposal_reasoning_tokens", "proposal_batch_size", "proposal_model"):
            self.assertIsNone(row[key])

    def test_batch_size_guards_against_double_count(self):
        # 批次级 usage 不能被当成单候选成本：batch_size 必须随行落盘，供下游去重
        cand = {"proposal_usage": {"prompt_tokens": 1128, "completion_tokens": 8,
                                   "total_tokens": 1136, "batch_size": 3}}
        append_verdicts(self.state, "run-u", (_record(cand),))
        row = read_verdicts(self.state.parent)[0]
        self.assertEqual(row["proposal_batch_size"], 3)
        self.assertIsNone(row["proposal_model"])  # 可选字段缺失不编造


if __name__ == "__main__":
    unittest.main()
