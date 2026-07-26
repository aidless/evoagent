import tempfile
import unittest
from pathlib import Path

from evoagent.core import candidate_id, load_json, save_json
from evoagent.l3_provisional import L3Policy, run_l3_provisional
from evoagent.stage_gates import make_evidence


class L3Tests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.r = Path(self.t.name)
        (self.r / ".evo").mkdir()
        save_json(self.r / ".evo/active.json", {"system_prompt": "base"})
        save_json(self.r / ".evo/version-registry.json", {"versions": {}, "history": []})

    def tearDown(self):
        self.t.cleanup()

    def candidate(self):
        return {"system_prompt": "candidate"}

    def bundle(self, candidate=None):
        candidate = candidate or self.candidate()
        return {
            "bundle_id": "test-bundle@abc",
            "sha256": "abc",
            "manifest": {"metadata": {"candidate_id": candidate_id(candidate)}},
        }

    def verifier(self, bundle_id):
        return {"valid": bundle_id == "test-bundle@abc", "reason": "ok"}

    def runner(self, stage, baseline, candidate):
        artifact = self.r / ".evo" / "test-artifacts" / f"{stage}.json"
        save_json(
            artifact,
            {
                "stage": stage,
                "baseline_id": candidate_id(baseline),
                "candidate_id": candidate_id(candidate),
                "real_execution": True,
            },
        )
        return make_evidence(
            stage,
            candidate_id(candidate),
            candidate_id(baseline),
            [stage],
            True,
            {"development": 20, "hidden_confirmation": 20, "trigger_safety": 10, "shadow": 30}[stage],
            decision={
                "cost": 1,
                "latency_s": 1,
                "evidence_kind": "benchmark_execution",
                "real_execution": True,
            },
            artifact=artifact,
        )

    def execute_l3(self, *, policy, health_check=None, runner=None, bundle=None, verifier=None):
        return run_l3_provisional(
            self.r,
            self.candidate(),
            runner or self.runner,
            health_check,
            policy,
            bundle if bundle is not None else self.bundle(),
            verifier if verifier is not None else self.verifier,
        )

    def test_dry_run_never_activates(self):
        before = load_json(self.r / ".evo/active.json")
        result = self.execute_l3(policy=L3Policy(dry_run=True))
        self.assertEqual(result["status"], "dry_run_passed")
        self.assertEqual(before, load_json(self.r / ".evo/active.json"))
        self.assertIn("would_write_binding", result)

    def test_activation_writes_binding_and_registry(self):
        result = self.execute_l3(policy=L3Policy(dry_run=False))
        self.assertEqual(result["status"], "activated_provisional")
        self.assertEqual(load_json(self.r / ".evo/active.json")["system_prompt"], "candidate")
        binding = load_json(self.r / ".evo/active-binding.json")
        self.assertEqual(binding["candidate_id"], candidate_id(self.candidate()))
        self.assertEqual(binding["bundle_id"], "test-bundle@abc")

    def test_health_failure_rolls_back_strategy_and_binding(self):
        before = load_json(self.r / ".evo/active.json")
        result = self.execute_l3(policy=L3Policy(dry_run=False), health_check=lambda _: {"healthy": False})
        self.assertEqual(result["status"], "rolled_back")
        self.assertTrue(result["rolled_back"])
        self.assertEqual(before, load_json(self.r / ".evo/active.json"))
        self.assertFalse((self.r / ".evo/active-binding.json").exists())

    def test_budget_failure_does_not_activate(self):
        result = self.execute_l3(policy=L3Policy(max_cost=0.1, dry_run=False))
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["activated"])

    def test_scaffold_without_artifacts_is_rejected(self):
        def scaffold(stage, baseline, candidate):
            return make_evidence(
                stage,
                candidate_id(candidate),
                candidate_id(baseline),
                [stage],
                True,
                {"development": 20, "hidden_confirmation": 20, "trigger_safety": 10, "shadow": 30}[stage],
                decision={"cost": 0, "latency_s": 0},
            )

        result = self.execute_l3(policy=L3Policy(dry_run=False), runner=scaffold)
        self.assertEqual(result["status"], "rejected")
        self.assertIn("missing_artifact:development", result["decision"]["reasons"])
        self.assertIn("unverified_execution:development", result["decision"]["reasons"])

    def test_missing_trusted_bundle_verifier_is_rejected(self):
        result = run_l3_provisional(
            self.r,
            self.candidate(),
            self.runner,
            policy=L3Policy(dry_run=False),
            bundle=self.bundle(),
            bundle_verifier=None,
        )
        self.assertEqual(result["status"], "rejected")
        self.assertIn("trusted_bundle_verifier_required", result["error"])


if __name__ == "__main__":
    unittest.main()
