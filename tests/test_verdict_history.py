# verdict 数据流测试：change_manifest 的 per-edit 判定落成可复算的 JSONL 历史，
# 供 P4 信任度打分器（eval-meta）与 P3 技能编译器共享同一份证据。
import json
import tempfile
import unittest
from pathlib import Path

from evoagent.cli import init
from evoagent.core import evolve, load_json, save_json
from evoagent.verdict_history import append_verdicts, read_verdicts, summarize

RECORD_FIX = {
    "id": "cand-1", "safe": True,
    "change_verdict": {
        "valid": True,
        "edits": {
            "e1": {"edit_id": "e1", "kind": "tool", "files": ["tools/normalize.py"],
                   "verdict": "effective_fix", "hits": ["case"],
                   "prediction_precision": 0.5,
                   "predicted_fix": ["case", "both"], "predicted_regression": []},
        },
        "campaign": {"prediction_precision": 0.5, "predicted_total": 2, "hit_total": 1},
    },
}
RECORD_NONE = {"id": "cand-2", "safe": True, "change_verdict": None}
RECORD_MALFORMED = {"id": "cand-3", "safe": False,
                    "change_verdict": {"valid": False,
                                       "reasons": ["change_manifest_malformed"], "edits": {}}}

PROPOSER_TMPL = '''import json, os
incumbent = json.loads(os.environ["EVO_INCUMBENT"])
incumbent["normalize_case"] = True
incumbent["change_manifest"] = json.loads({manifest})
print(json.dumps([incumbent]))
'''


class AppendReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / ".evo"
        self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_only_manifest_candidates_appended(self):
        # GREEN：无 manifest 的候选不写（历史里不该有噪声行）
        written = append_verdicts(self.state, "run-1", (RECORD_FIX, RECORD_NONE))
        self.assertEqual(written, 1)
        rows = read_verdicts(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidate_id"], "cand-1")

    def test_edit_rows_flattened(self):
        # GREEN：每笔 edit 一行证据，带 kind/verdict/precision，供按 kind 聚合
        append_verdicts(self.state, "run-1", (RECORD_FIX,))
        row = read_verdicts(self.root)[0]
        self.assertEqual(row["edits"][0]["edit_id"], "e1")
        self.assertEqual(row["edits"][0]["kind"], "tool")
        self.assertEqual(row["edits"][0]["verdict"], "effective_fix")
        self.assertAlmostEqual(row["prediction_precision"], 0.5)

    def test_malformed_recorded_as_invalid(self):
        # GREEN：fail-closed 的畸形 manifest 也要留痕（P4 要能看见被拦的次数）
        append_verdicts(self.state, "run-1", (RECORD_MALFORMED,))
        row = read_verdicts(self.root)[0]
        self.assertFalse(row["valid"])
        self.assertEqual(row["edits"], [])

    def test_bad_line_skipped(self):
        # GREEN：历史文件里混入坏行时只跳过，不抛异常
        append_verdicts(self.state, "run-1", (RECORD_FIX,))
        with open(self.state / "verdicts.jsonl", "a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        self.assertEqual(len(read_verdicts(self.root)), 1)


class SummarizeTests(unittest.TestCase):
    def test_kind_precision_aggregated(self):
        # GREEN：按 edit kind 聚合预测精度与判定分布
        rows = [
            {"candidate_id": "a", "valid": True, "prediction_precision": 0.5,
             "edits": [{"edit_id": "e1", "kind": "tool", "verdict": "effective_fix",
                        "prediction_precision": 0.5}]},
            {"candidate_id": "b", "valid": True, "prediction_precision": 1.0,
             "edits": [{"edit_id": "e1", "kind": "tool", "verdict": "no_effect",
                        "prediction_precision": 1.0},
                       {"edit_id": "e2", "kind": "prompt", "verdict": "regression",
                        "prediction_precision": 0.0}]},
            {"candidate_id": "c", "valid": False, "prediction_precision": None,
             "edits": []},
        ]
        stats = summarize(rows)
        self.assertEqual(stats["campaigns"], 3)
        self.assertEqual(stats["invalid"], 1)
        self.assertAlmostEqual(stats["kinds"]["tool"]["mean_precision"], 0.75)
        self.assertEqual(stats["kinds"]["tool"]["edits"], 2)
        self.assertEqual(stats["kinds"]["prompt"]["verdicts"]["regression"], 1)
        self.assertAlmostEqual(stats["overall_precision"], 0.75)

    def test_empty_history(self):
        stats = summarize([])
        self.assertEqual(stats["campaigns"], 0)
        self.assertIsNone(stats["overall_precision"])


class EvolveIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = Path(__file__).parents[1]
        for name in ("seed.json", "evo.json"):
            (self.root / name).write_bytes((source / name).read_bytes())
        config = load_json(self.root / "evo.json")
        config.setdefault("statistical_gate", {})["enabled"] = False
        save_json(self.root / "evo.json", config)
        (self.root / "examples").mkdir()
        for name in ("benchmark.json", "evaluator.py"):
            (self.root / "examples" / name).write_bytes((source / "examples" / name).read_bytes())
        init(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_evolve_writes_verdict_history(self):
        # GREEN：evolve 跑完，带 manifest 的候选在 .evo/verdicts.jsonl 留一行
        manifest = {"edits": [{"edit_id": "e1", "kind": "tool",
                               "target_files": ["tools/normalize.py"],
                               "predicted_fix": ["case"], "predicted_regression": [],
                               "rationale": "大小写归一化"}]}
        (self.root / "proposer_test.py").write_text(
            PROPOSER_TMPL.format(manifest=json.dumps(json.dumps(manifest))))
        config = load_json(self.root / "evo.json")
        config["proposer_command"] = "python3 proposer_test.py"
        save_json(self.root / "evo.json", config)
        evolve(self.root)
        rows = read_verdicts(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["edits"][0]["kind"], "tool")
        self.assertAlmostEqual(rows[0]["prediction_precision"], 1.0)


if __name__ == "__main__":
    unittest.main()