import json
import tempfile
import unittest
from pathlib import Path

from evoagent.autonomy import EvolutionPolicy, evolve_autonomously
from evoagent.cli import init
from evoagent.core import EvalResult, load_json, propose, save_json


class AutonomousEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = Path(__file__).parents[1]
        for name in ("seed.json", "evo.json"):
            (self.root / name).write_bytes((source / name).read_bytes())
        (self.root / "examples").mkdir()
        for name in ("benchmark.json", "evaluator.py"):
            (self.root / "examples" / name).write_bytes(
                (source / "examples" / name).read_bytes()
            )
        config = load_json(self.root / "evo.json")
        config["statistical_gate"]["enabled"] = False
        save_json(self.root / "evo.json", config)
        init(self.root)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def evaluator(root, candidate):
        score = float(candidate.get("fitness", 0))
        total = 10
        passed = round(score * total)
        outcomes = tuple(
            {
                "task_id": str(i),
                "passed": i < passed,
                "score": 1.0 if i < passed else 0.0,
                "cost": 0.0,
                "latency_s": 0.01,
                "safety_violations": 0,
                "capabilities": {"core": score},
                "details": {},
            }
            for i in range(total)
        )
        return EvalResult(score, passed, total, tuple(str(i) for i in range(passed, total)), 0.1, outcomes)

    def test_multi_round_learning_promotes_best_candidate(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})

        def proposer(root, incumbent, failures):
            return [{"fitness": min(1.0, incumbent["fitness"] + 0.3)}]

        result = evolve_autonomously(
            self.root,
            self.evaluator,
            proposer,
            EvolutionPolicy(3, 3, 2, 0.1, False),
        )
        self.assertTrue(result.report["promoted"])
        self.assertEqual(load_json(self.root / ".evo" / "active.json")["fitness"], 1.0)
        self.assertEqual(len(result.report["rounds"]), 3)
        self.assertTrue(result.report_path.exists())

    def test_duplicate_candidates_are_not_re_evaluated(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})
        calls = []

        def evaluator(root, candidate):
            calls.append(candidate["fitness"])
            return self.evaluator(root, candidate)

        def proposer(root, incumbent, failures):
            return [{"fitness": 0.5}, {"fitness": 0.5}]

        result = evolve_autonomously(
            self.root, evaluator, proposer, EvolutionPolicy(2, 5, 1, 0.1, False)
        )
        self.assertEqual(calls, [0.2, 0.5])
        statuses = [x["status"] for x in result.report["rounds"][0]["candidates"]]
        self.assertEqual(statuses, ["evaluated", "duplicate"])

    def test_unsafe_candidate_is_audited_and_not_run(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})
        calls = []

        def evaluator(root, candidate):
            calls.append(candidate)
            return self.evaluator(root, candidate)

        def proposer(root, incumbent, failures):
            return [{"fitness": 1.0, "instruction": "shutdown /s"}]

        result = evolve_autonomously(
            self.root, evaluator, proposer, EvolutionPolicy(1, 5, 1, 0.1, False)
        )
        self.assertFalse(result.report["promoted"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            result.report["rounds"][0]["candidates"][0]["status"], "rejected"
        )

    def test_statistical_rejection_prevents_activation(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})
        config = load_json(self.root / "evo.json")
        config["statistical_gate"] = {
            "enabled": True,
            "min_gain": 0.01,
            "bootstrap_iterations": 200,
        }
        save_json(self.root / "evo.json", config)

        result = evolve_autonomously(
            self.root,
            self.evaluator,
            lambda *_: [{"fitness": 0.3}],
            EvolutionPolicy(1, 3, 1, 0.01, True),
        )
        self.assertFalse(result.report["promoted"])
        self.assertEqual(result.report["stop_reason"], "promotion_gate_rejected")
        self.assertEqual(load_json(self.root / ".evo" / "active.json")["fitness"], 0.2)



    def test_eligible_candidate_wins_over_higher_rejected_candidate(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})
        config = load_json(self.root / "evo.json")
        config["statistical_gate"]["enabled"] = False
        save_json(self.root / "evo.json", config)

        def proposer(root, incumbent, failures):
            return [{"fitness": 0.9}, {"fitness": 0.7}]

        from unittest.mock import patch
        decisions = [
            {"promote": False, "reasons": ["safety_violation"]},
            {"promote": True, "reasons": []},
        ]
        with patch("evoagent.autonomy._gate", side_effect=decisions):
            result = evolve_autonomously(
                self.root, self.evaluator, proposer, EvolutionPolicy(1, 3, 1, 0.1, True)
            )
        self.assertTrue(result.report["promoted"])
        self.assertEqual(load_json(self.root / ".evo" / "active.json")["fitness"], 0.7)
        self.assertEqual(result.report["best_observed"]["evaluation"]["score"], 0.9)
        self.assertEqual(result.report["winner"]["evaluation"]["score"], 0.7)

    def test_round_experience_uses_frozen_parent(self):
        save_json(self.root / ".evo" / "active.json", {"fitness": 0.2})
        result = evolve_autonomously(
            self.root,
            self.evaluator,
            lambda *_: [{"fitness": 0.5}, {"fitness": 0.6}],
            EvolutionPolicy(1, 3, 1, 0.1, False),
        )
        memory = load_json(self.root / ".evo" / "experience.json")["experiences"]
        self.assertEqual(len({x["parent_id"] for x in memory}), 1)
        self.assertEqual([round(x["gain"], 2) for x in memory], [0.3, 0.4])


if __name__ == "__main__":
    unittest.main()
