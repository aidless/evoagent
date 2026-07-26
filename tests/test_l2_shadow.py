import tempfile
import unittest
from pathlib import Path

from evoagent.core import candidate_id, load_json, save_json
from evoagent.l2_shadow import run_l2_shadow
from evoagent.stage_gates import make_evidence


class L2ShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name);(self.root / ".evo").mkdir();save_json(self.root / ".evo" / "active.json", {"system_prompt": "base"})
    def tearDown(self):self.temp.cleanup()
    def runner(self, stage, baseline, candidate):
        sizes = {"development": 20, "hidden_confirmation": 20, "trigger_safety": 10, "shadow": 30}
        return make_evidence(stage, candidate_id(candidate), candidate_id(baseline), [stage], True, sizes[stage])
    def test_l2_never_changes_active(self):
        before = load_json(self.root / ".evo" / "active.json");result = run_l2_shadow(self.root, {"system_prompt": "candidate"}, self.runner)
        self.assertEqual(before, load_json(self.root / ".evo" / "active.json"));self.assertFalse(result.report["active_changed"]);self.assertTrue(result.report["decision"]["shadow_ready"])
    def test_l2_stops_after_safety_failure(self):
        calls=[]
        def runner(stage, baseline, candidate):
            calls.append(stage);return make_evidence(stage,candidate_id(candidate),candidate_id(baseline),[stage],stage!="trigger_safety",20,safety_violations=1 if stage=="trigger_safety" else 0)
        result=run_l2_shadow(self.root,{"system_prompt":"candidate"},runner);self.assertEqual(calls,["development","hidden_confirmation","trigger_safety"]);self.assertFalse(result.report["decision"]["passed"])
if __name__=='__main__':unittest.main()
