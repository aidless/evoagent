import json
import tempfile
import unittest
from pathlib import Path

from evoagent.cli import init
from evoagent.core import evaluate, evolve, load_json, rollback, safety_check


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = Path(__file__).parents[1]
        for name in ("seed.json", "evo.json"):
            (self.root / name).write_bytes((source / name).read_bytes())
        config = load_json(self.root / "evo.json")
        config.setdefault("statistical_gate", {})["enabled"] = False
        from evoagent.core import save_json
        save_json(self.root / "evo.json", config)
        (self.root / "examples").mkdir()
        for name in ("benchmark.json", "evaluator.py"):
            (self.root / "examples" / name).write_bytes((source / "examples" / name).read_bytes())
        init(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_evolution_promotes_better_candidate(self):
        report = evolve(self.root)
        self.assertTrue(report["promoted"])
        active = load_json(self.root / ".evo" / "active.json")
        self.assertTrue(active["normalize_case"] and active["trim_whitespace"])
        self.assertEqual(report["active_score"], 1.0)

    def test_rollback_restores_seed(self):
        evolve(self.root)
        rollback(self.root)
        self.assertEqual(load_json(self.root / ".evo" / "active.json"), load_json(self.root / "seed.json"))

    def test_evaluator_emits_per_case_outcomes(self):
        result = evaluate(self.root, load_json(self.root / "seed.json"))
        self.assertEqual(len(result.outcomes), 4)
        self.assertEqual({x["task_id"] for x in result.outcomes}, {"exact", "case", "space", "both"})
        self.assertTrue(all(x["latency_s"] >= 0 for x in result.outcomes))

    def test_statistical_gate_blocks_tiny_sample_promotion(self):
        config = load_json(self.root / "evo.json")
        config["statistical_gate"] = {"enabled": True, "bootstrap_iterations": 500}
        from evoagent.core import save_json
        save_json(self.root / "evo.json", config)
        report = evolve(self.root)
        self.assertTrue(report["legacy_promoted"])
        self.assertFalse(report["promoted"])
        self.assertIsNotNone(report["statistical_decision"])

    def test_safety_gate(self):
        config = load_json(self.root / "evo.json")
        safe, reason = safety_check({"instruction": "please shutdown /s"}, config)
        self.assertFalse(safe)
        self.assertIn("forbidden_token", reason)


if __name__ == "__main__":
    unittest.main()
