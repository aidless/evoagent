import tempfile
import unittest
from pathlib import Path

from evoagent.core import EvalResult, save_json
from evoagent.experience import (
    AdaptiveProposer,
    ExperienceStore,
    apply_patch,
    diagnose,
    diff,
)


def result(score, failed_ids=(), categories=None):
    categories = categories or {}
    total = 4
    outcomes = []
    for i in range(total):
        task_id = failed_ids[i] if i < len(failed_ids) else f"ok:{i}"
        passed = i >= len(failed_ids)
        outcomes.append(
            {
                "task_id": task_id,
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "cost": 0.0,
                "latency_s": 0.01,
                "safety_violations": 0,
                "capabilities": {"reasoning": 0.25 if not passed else 1.0},
                "details": {"category": categories.get(task_id, task_id.split(":")[0])},
            }
        )
    return EvalResult(score, total - len(failed_ids), total, tuple(failed_ids), 0.1, tuple(outcomes))


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        save_json(
            self.root / "evo.json",
            {
                "mutations": [],
                "adaptive_proposer": {"memory_candidates": 5, "min_trials": 1},
            },
        )
        self.store = ExperienceStore(self.root / ".evo" / "experience.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_diagnosis_groups_failures_and_capability_gaps(self):
        diagnosis = diagnose(result(0.5, ("math:1", "date:2")))
        self.assertEqual(diagnosis.categories, {"math": 1, "date": 1})
        self.assertEqual(diagnosis.capability_gaps["reasoning"], 0.75)
        self.assertEqual(diagnosis.failure_rate, 0.5)

    def test_experience_ranks_positive_mutations(self):
        base = {"mode": "base"}
        good = {"mode": "verify"}
        bad = {"mode": "fast"}
        baseline = result(0.25, ("math:1", "math:2", "date:1"))
        self.store.record("r1", base, good, baseline, result(0.75, ("date:1",)), {"promote": True})
        self.store.record("r2", base, bad, baseline, result(0.0, ("math:1", "math:2", "date:1", "logic:1")), {"promote": False})
        self.assertEqual(self.store.successful_patches(), [{"mode": "verify"}])
        self.assertEqual(self.store.summary()["positive"], 1)

    def test_adaptive_proposer_reuses_memory_and_deduplicates(self):
        base = {"mode": "base", "temperature": 0}
        baseline = result(0.25, ("math:1", "math:2", "date:1"))
        good = {"mode": "verify", "temperature": 0}
        self.store.record("r1", base, good, baseline, result(0.75, ("date:1",)), {"promote": True})
        proposer = AdaptiveProposer(self.store, lambda *_: [good, good])
        proposals = proposer(self.root, base, ("math:1",))
        self.assertEqual(proposals, [good])

    def test_failure_specific_mutation_is_applied(self):
        config = {
            "mutations": [],
            "adaptive_proposer": {
                "memory_candidates": 0,
                "failure_mutations": {"math": {"tool": "calculator"}},
            },
        }
        save_json(self.root / "evo.json", config)
        proposer = AdaptiveProposer(self.store)
        self.assertEqual(
            proposer(self.root, {"mode": "base"}, ("math:case-1",)),
            [{"mode": "base", "tool": "calculator"}],
        )

    def test_diff_and_apply_patch_round_trip(self):
        parent = {"a": 1, "b": 2}
        child = {"a": 1, "b": 3, "c": 4}
        self.assertEqual(apply_patch(parent, diff(parent, child)), child)


if __name__ == "__main__":
    unittest.main()
