import unittest
from pathlib import Path

from evoagent.benchmark_registry_v2 import BenchmarkRegistryV2
from evoagent.p0_evaluation import evaluate_strategy


class P0EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        root = project.parent / f"{project.name}-private" / "benchmark-registry-v2"
        if not (root / "tasks.json").exists():
            raise unittest.SkipTest(f"frozen P0 registry lives in the private sibling repo, absent at {root}")
        cls.registry = BenchmarkRegistryV2.load(root / "tasks.json", root / "answer-key.json")

    def test_real_deterministic_runner_uses_frozen_stage(self):
        run = evaluate_strategy(
            self.registry,
            {"normalize_case": True, "trim_whitespace": True},
            stage="development",
        )
        self.assertEqual(len(run.outcomes), 45)
        self.assertTrue(all(row.details["real_execution"] for row in run.outcomes))
        self.assertEqual({row.details["domain"] for row in run.outcomes}, {"date", "logic", "tool"})
        self.assertTrue(all(row.passed for row in run.outcomes))

    def test_missing_normalization_is_measurably_worse(self):
        baseline = evaluate_strategy(self.registry, {}, stage="development")
        candidate = evaluate_strategy(
            self.registry,
            {"normalize_case": True, "trim_whitespace": True},
            stage="development",
        )
        self.assertGreater(sum(row.score for row in candidate.outcomes), sum(row.score for row in baseline.outcomes))


if __name__ == "__main__":
    unittest.main()
