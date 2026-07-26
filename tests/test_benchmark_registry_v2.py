import json
import tempfile
import unittest
from pathlib import Path

from evoagent.benchmark_registry_v2 import BenchmarkRegistryV2, BenchmarkTaskV2, write_registry


class BenchmarkRegistryV2Tests(unittest.TestCase):
    def task(self, task_id="t1", stage="development", value="x"):
        return BenchmarkTaskV2(
            task_id=task_id,
            domain="tool",
            stage=stage,
            input=value,
            expected=value,
            success_criteria={"type": "exact_string"},
            source="unit-test",
            license="test-only",
            snapshot_date="2026-07-25",
            hidden=stage != "development",
            contamination_checked=True,
        )

    def test_answers_are_sealed_and_bound_to_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "tasks.json"
            key = root / "answer-key.json"
            write_registry(
                [self.task(), self.task("t2", "hidden_confirmation", "y")],
                manifest,
                key,
                split_seed=7,
            )
            public = BenchmarkRegistryV2.load(manifest)
            self.assertTrue(all(task.expected is None for task in public.tasks))
            evaluator = BenchmarkRegistryV2.load(manifest, key)
            self.assertEqual(evaluator.get("t2").expected, "y")
            payload = json.loads(key.read_text())
            payload["manifest_sha256"] = "0" * 64
            key.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "not bound"):
                BenchmarkRegistryV2.load(manifest, key)

    def test_frozen_answer_key_hash_detects_answer_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "tasks.json"
            key = root / "answer-key.json"
            result = write_registry([self.task()], manifest, key, split_seed=7)
            payload = json.loads(key.read_text())
            payload["answers"][0]["expected"] = "tampered"
            key.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "answer key hash"):
                BenchmarkRegistryV2.load(
                    manifest,
                    key,
                    expected_manifest_sha256=result["manifest_sha256"],
                    expected_answer_key_sha256=result["answer_key_sha256"],
                )

    def test_duplicate_content_is_rejected(self):
        a = self.task("a", value="same")
        b = self.task("b", stage="shadow", value="same")
        result = BenchmarkRegistryV2([a, b]).validate(require_answers=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any(reason.startswith("duplicate_content") for reason in result["reasons"]))

    def test_frozen_p0_registry_has_required_360_split(self):
        project = Path(__file__).resolve().parents[1]
        root = project.parent / f"{project.name}-private" / "benchmark-registry-v2"
        registry = BenchmarkRegistryV2.load(root / "tasks.json", root / "answer-key.json")
        summary = registry.summary()
        self.assertEqual(summary["tasks"], 360)
        self.assertEqual(summary["by_stage"], {
            "development": 120,
            "hidden_confirmation": 80,
            "trigger_safety": 60,
            "shadow": 100,
        })
        self.assertTrue(all(n == 45 for n in summary["by_domain"].values()))


if __name__ == "__main__":
    unittest.main()
