import tempfile
import unittest
from pathlib import Path

from evoagent.active_binding import build_active_binding, verify_active_binding
from evoagent.core import candidate_id


class ActiveBindingTests(unittest.TestCase):
    def setUp(self):
        self.strategy = {"system_prompt": "candidate"}
        self.bundle = {
            "bundle_id": "bundle@abc",
            "sha256": "abc",
            "manifest": {"metadata": {"candidate_id": candidate_id(self.strategy)}},
        }

    def test_complete_binding_verifies_and_tamper_fails(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / "evidence.json"
            evidence.write_text("verified")
            binding = build_active_binding(self.strategy, self.bundle, "tx-1", evidence)
            self.assertTrue(verify_active_binding(binding, self.strategy, self.bundle, evidence)["valid"])
            evidence.write_text("changed")
            result = verify_active_binding(binding, self.strategy, self.bundle, evidence)
            self.assertFalse(result["valid"])
            self.assertIn("evidence_hash_mismatch", result["reasons"])

    def test_bundle_without_candidate_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / "evidence.json"
            evidence.write_text("verified")
            bundle = {**self.bundle, "manifest": {"metadata": {}}}
            with self.assertRaisesRegex(ValueError, "not bound"):
                build_active_binding(self.strategy, bundle, "tx-1", evidence)


if __name__ == "__main__":
    unittest.main()
