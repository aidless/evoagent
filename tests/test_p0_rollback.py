import tempfile
import unittest
from pathlib import Path

from evoagent.benchmark_registry_v2 import sha256_file
from evoagent.core import candidate_id, load_json, save_json
from evoagent.p0_rollback import assess_rollback, rollback_from_evidence
from evoagent.version_registry import VersionRegistry


class P0RollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        state = self.root / ".evo"
        state.mkdir()
        self.baseline = {"system_prompt": "baseline"}
        self.candidate = {"system_prompt": "candidate"}
        save_json(state / "active.json", self.candidate)
        save_json(state / "active-binding.json", {"candidate_id": candidate_id(self.candidate)})
        self.deterministic_path = state / "benchmark-registry-v2" / "deterministic.json"
        self.safety_path = state / "benchmark-registry-v2" / "safety.json"
        self.baseline_path = state / "transactions" / "baseline.json"
        save_json(self.baseline_path, self.baseline)
        save_json(self.deterministic_path, {
            "baseline_id": candidate_id(self.baseline),
            "candidate_id": candidate_id(self.candidate),
            "overall": {"promotion_gate": {"promote": False, "mean_gain": 0.0}},
        })
        save_json(self.safety_path, {
            "baseline": {"candidate_id": candidate_id(self.baseline), "safety_violations": 1, "harmful_refusal_rate": 0.9},
            "candidate": {"candidate_id": candidate_id(self.candidate), "safety_violations": 2, "harmful_refusal_rate": 0.8},
            "calibration_gate": {"passed": False},
        })
        save_json(state / "benchmark-registry-v2" / "current-status.json", {
            "report_sha256": sha256_file(self.deterministic_path),
            "safety_calibration_sha256": sha256_file(self.safety_path),
        })
        registry = VersionRegistry(state / "version-registry.json")
        registry.register(candidate_id(self.candidate), "agent_strategy", "provisional")

    def tearDown(self):
        self.temp.cleanup()

    def test_assessment_detects_safety_regression(self):
        result = assess_rollback(load_json(self.deterministic_path), load_json(self.safety_path))
        self.assertTrue(result["rollback_required"])
        self.assertIn("candidate_safety_regression", result["reasons"])

    def test_dry_run_does_not_change_active(self):
        result = rollback_from_evidence(
            self.root, self.deterministic_path, self.safety_path, self.baseline_path, apply=False
        )
        self.assertEqual(result["status"], "would_rollback")
        self.assertEqual(load_json(self.root / ".evo/active.json"), self.candidate)

    def test_apply_restores_baseline_and_downgrades_candidate(self):
        result = rollback_from_evidence(
            self.root, self.deterministic_path, self.safety_path, self.baseline_path, apply=True
        )
        self.assertTrue(result["applied"])
        self.assertEqual(load_json(self.root / ".evo/active.json"), self.baseline)
        self.assertFalse((self.root / ".evo/active-binding.json").exists())
        registry = VersionRegistry(self.root / ".evo/version-registry.json")
        self.assertEqual(registry.get(candidate_id(self.candidate))["level"], "experimental")
        self.assertEqual(registry.get(candidate_id(self.baseline))["level"], "experimental")


if __name__ == "__main__":
    unittest.main()
