"""cost_layer_reprobe 的判据与假阳守卫。

关键：判决必须机械按跑前声明（层样本量/level 结构），不能事后挑层挑 kind；
回填必须只用真测量 join，join 不到填 None 而不是编造 0（否则延迟低层被伪造成 0 秒）。
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "campaigns" / "trust-probe-01" / "cost_layer_reprobe.py"


def _load():
    spec = importlib.util.spec_from_file_location("cost_layer_reprobe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(cid: str, precision: float, kind: str = "prompt") -> dict:
    return {
        "run_id": "r", "candidate_id": cid, "valid": True, "reasons": [],
        "prediction_precision": precision, "predicted_total": 1, "hit_total": int(precision),
        "candidate_regression_rate": 0.0, "edit_regression_rate": 0.0,
        "edits": [{"edit_id": f"e-{cid}", "kind": kind, "files": ["x.yaml"],
                   "verdict": "effective_fix", "hits": ["c01"],
                   "prediction_precision": precision,
                   "predicted_fix": ["c01"], "predicted_regression": []}],
    }


class CostLayerTests(unittest.TestCase):
    def test_load_true_latency_sums_outcomes(self):
        m = _load()
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td)
            (runs / "runA.json").write_text(json.dumps({
                "run_id": "runA",
                "candidates": [{"id": "c1", "evaluation": {"outcomes": [
                    {"latency_s": 0.1}, {"latency_s": 0.2}]}}],
            }), encoding="utf-8")
            truth = m.load_true_latency(runs)
            self.assertAlmostEqual(truth[("runA", "c1")], 0.3)

    def test_backfill_missing_join_is_none_not_zero(self):
        m = _load()
        rows = m.backfill([_row("c1", 0.5)], {("r", "c1"): 0.12})
        self.assertAlmostEqual(rows[0]["evaluation_latency_s"], 0.12)
        missing = m.backfill([_row("c2", 0.5)], {})
        self.assertIsNone(missing[0]["evaluation_latency_s"])

    def test_assign_layers_splits_by_latency_order(self):
        m = _load()
        rows = [dict(_row(f"c{i}", 0.5), evaluation_latency_s=float(i))
                for i in range(9)]
        layers = m.assign_layers(rows)
        self.assertEqual([len(layers[f"L{i}"]) for i in (1, 2, 3)], [3, 3, 3])
        self.assertEqual(layers["L1"][0]["candidate_id"], "c0")
        self.assertEqual(layers["L3"][-1]["candidate_id"], "c8")

    def test_judge_rejects_uniform_levels(self):
        m = _load()
        rep = {f"L{i}": {"kinds": {"prompt": {"level": "L3", "n_edits": 10}}}
               for i in (1, 2, 3)}
        self.assertEqual(m.judge(rep, "prompt")["verdict"], "REJECT_NO_STRUCTURE")

    def test_judge_supports_monotonic_levels(self):
        m = _load()
        rep = {"L1": {"kinds": {"prompt": {"level": "L2", "n_edits": 10}}},
               "L2": {"kinds": {"prompt": {"level": "L2", "n_edits": 10}}},
               "L3": {"kinds": {"prompt": {"level": "L3", "n_edits": 10}}}}
        self.assertEqual(m.judge(rep, "prompt")["verdict"], "SUPPORT")

    def test_judge_no_power_when_layer_under_min_edits(self):
        m = _load()
        rep = {"L1": {"kinds": {"prompt": {"level": "L2", "n_edits": 10}}},
               "L2": {"kinds": {"prompt": {"level": "L3", "n_edits": 2}}},
               "L3": {"kinds": {"prompt": {"level": "L3", "n_edits": 10}}}}
        self.assertEqual(m.judge(rep, "prompt")["verdict"], "NO_POWER")

    def test_judge_non_monotonic_rejected(self):
        m = _load()
        rep = {"L1": {"kinds": {"prompt": {"level": "L2", "n_edits": 10}}},
               "L2": {"kinds": {"prompt": {"level": "L3", "n_edits": 10}}},
               "L3": {"kinds": {"prompt": {"level": "L2", "n_edits": 10}}}}
        self.assertEqual(m.judge(rep, "prompt")["verdict"], "REJECT_NO_STRUCTURE")


if __name__ == "__main__":
    unittest.main()
