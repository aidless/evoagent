# change_manifest 接线测试：evolve 循环里的 per-edit 对账端到端行为。
# RED→GREEN：先在无实现（stash）状态下确认全部失败，再恢复实现确认通过。
import json
import tempfile
import unittest
from pathlib import Path

from evoagent.cli import init
from evoagent.core import evolve, load_json, save_json

# 提案器：读 EVO_INCUMBENT，追加 normalize_case + 内嵌 manifest，输出 JSON 列表
PROPOSER_TMPL = '''import json, os
incumbent = json.loads(os.environ["EVO_INCUMBENT"])
incumbent["normalize_case"] = True
incumbent["change_manifest"] = json.loads({manifest})
print(json.dumps([incumbent]))
'''


class ChangeManifestWiringTests(unittest.TestCase):
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

    def _run_with_manifest(self, manifest: dict) -> dict:
        # manifest 直接内嵌进提案器脚本，避免 shell 转义问题
        (self.root / "proposer_test.py").write_text(
            PROPOSER_TMPL.format(manifest=json.dumps(json.dumps(manifest))))
        config = load_json(self.root / "evo.json")
        config["proposer_command"] = "python3 proposer_test.py"
        save_json(self.root / "evo.json", config)
        return evolve(self.root)

    def test_effective_fix_end_to_end(self):
        # GREEN：normalize_case 实际只翻转 case（both 还差 trim）——
        # 预测 case+both 命中 case，precision=0.5，verdict=effective_fix
        manifest = {"edits": [{"edit_id": "e1", "kind": "tool",
                               "target_files": ["tools/normalize.py"],
                               "predicted_fix": ["case", "both"],
                               "predicted_regression": [],
                               "rationale": "大小写归一化"}]}
        report = self._run_with_manifest(manifest)
        v = report["candidates"][0]["change_verdict"]
        self.assertEqual(v["edits"]["e1"]["verdict"], "effective_fix")
        self.assertEqual(v["edits"]["e1"]["hits"], ["case"])
        self.assertAlmostEqual(v["campaign"]["prediction_precision"], 0.5)
        self.assertEqual(report["change_rollback_plan"]["keep"], ["e1"])

    def test_overprediction_precision_halved(self):
        # GREEN：预测 space 也会翻转（实际需要 trim_whitespace）→ precision=1/3
        manifest = {"edits": [{"edit_id": "e1", "kind": "tool",
                               "target_files": ["tools/normalize.py"],
                               "predicted_fix": ["case", "space", "both"],
                               "predicted_regression": [],
                               "rationale": "过度声明"}]}
        report = self._run_with_manifest(manifest)
        v = report["candidates"][0]["change_verdict"]
        self.assertAlmostEqual(v["campaign"]["prediction_precision"], 1 / 3)
        self.assertEqual(v["edits"]["e1"]["hits"], ["case"])

    def test_malformed_manifest_fail_closed(self):
        # RED 对照：manifest 不是 {"edits": [...]} 形状 → fail-closed 判定
        report = self._run_with_manifest("oops")
        v = report["candidates"][0]["change_verdict"]
        self.assertFalse(v["valid"])
        self.assertIn("change_manifest_malformed", v["reasons"])

    def test_no_manifest_keeps_old_behavior(self):
        # GREEN：默认声明式 mutation（无 manifest）→ change_verdict 全 None，
        # 报告里没有 change_rollback_plan 键，行为与旧版完全一致
        report = evolve(self.root)
        self.assertTrue(report["promoted"])
        self.assertTrue(all(r["change_verdict"] is None for r in report["candidates"]))
        self.assertNotIn("change_rollback_plan", report)


if __name__ == "__main__":
    unittest.main()
