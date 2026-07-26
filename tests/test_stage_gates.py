import tempfile
import unittest
from pathlib import Path

from evoagent.stage_gates import FourStagePolicy, evaluate_four_stage, make_evidence


class FourStageGateTests(unittest.TestCase):
    def evidence(self, stage, tasks, n=30, passed=True, safety=0, artifact=None):
        return make_evidence(stage, "cand", "base", tasks, passed, n, safety, artifact=artifact)

    def complete(self):
        return [
            self.evidence("development", ["dev-1"], 30),
            self.evidence("hidden_confirmation", ["hidden-1"], 30),
            self.evidence("trigger_safety", ["trigger-1"], 20),
            self.evidence("shadow", ["shadow-1"], 40),
        ]

    def test_l2_all_stages_pass_but_do_not_auto_promote(self):
        result = evaluate_four_stage("cand", "base", self.complete())
        self.assertTrue(result["passed"])
        self.assertTrue(result["shadow_ready"])
        self.assertFalse(result["auto_promote"])

    def test_missing_hidden_fails_closed(self):
        result = evaluate_four_stage("cand", "base", [x for x in self.complete() if x.stage != "hidden_confirmation"])
        self.assertFalse(result["passed"])
        self.assertIn("missing:hidden_confirmation", result["reasons"])

    def test_trigger_safety_violation_blocks(self):
        items = self.complete();items[2] = self.evidence("trigger_safety", ["trigger-1"], 20, True, 1)
        result = evaluate_four_stage("cand", "base", items)
        self.assertIn("safety_violation:trigger_safety", result["reasons"])

    def test_task_set_reuse_is_rejected(self):
        items = [self.evidence(stage, ["same"], 40) for stage in ("development", "hidden_confirmation", "trigger_safety", "shadow")]
        self.assertIn("task_set_reuse", evaluate_four_stage("cand", "base", items)["reasons"])

    def test_identity_mismatch_is_rejected(self):
        items = self.complete();bad = items[1];items[1] = type(bad)(bad.stage, "other", bad.baseline_id, bad.task_set_hash, bad.passed, bad.n)
        self.assertIn("identity_mismatch:hidden_confirmation", evaluate_four_stage("cand", "base", items)["reasons"])

    def test_changed_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "evidence.json";artifact.write_text("valid")
            items = self.complete();items[0] = self.evidence("development", ["dev-1"], 30, artifact=artifact);artifact.write_text("changed")
            self.assertIn("artifact_changed:development", evaluate_four_stage("cand", "base", items)["reasons"])

    def test_l3_can_auto_promote_after_all_gates(self):
        policy = FourStagePolicy(autonomy_level="L3_PROVISIONAL")
        self.assertTrue(evaluate_four_stage("cand", "base", self.complete(), policy)["auto_promote"])

    def test_strict_l3_rejects_scaffold_evidence(self):
        policy = FourStagePolicy(
            require_artifacts=True,
            require_real_execution=True,
            autonomy_level="L3_PROVISIONAL",
        )
        result = evaluate_four_stage("cand", "base", self.complete(), policy)
        self.assertFalse(result["auto_promote"])
        self.assertIn("missing_artifact:development", result["reasons"])
        self.assertIn("unverified_execution:development", result["reasons"])


if __name__ == "__main__":
    unittest.main()
