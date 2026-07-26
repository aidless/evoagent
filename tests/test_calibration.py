import unittest

from evoagent.calibration import SelectiveRecord, evaluate_calibration_gate, selective_metrics


class CalibrationTests(unittest.TestCase):
    def test_selective_metrics_separate_coverage_and_abstention(self):
        metrics = selective_metrics([
            SelectiveRecord("a", True, False, True),
            SelectiveRecord("b", True, True, False),
            SelectiveRecord("c", False, True, False),
            SelectiveRecord("d", False, False, False),
        ])
        self.assertEqual(metrics["coverage"], 0.5)
        self.assertEqual(metrics["selective_accuracy"], 0.5)
        self.assertEqual(metrics["appropriate_abstention_rate"], 0.5)
        self.assertEqual(metrics["unnecessary_abstention_rate"], 0.5)

    def test_gate_rejects_over_abstention(self):
        baseline = {
            "coverage": 0.9,
            "selective_accuracy": 0.9,
            "appropriate_abstention_rate": 0.8,
            "unnecessary_abstention_rate": 0.05,
        }
        candidate = {**baseline, "coverage": 0.8, "unnecessary_abstention_rate": 0.09}
        result = evaluate_calibration_gate(baseline, candidate)
        self.assertFalse(result["passed"])
        self.assertIn("coverage_regression", result["reasons"])
        self.assertIn("unnecessary_abstention_regression", result["reasons"])

    def test_missing_denominator_fails_closed(self):
        metrics = selective_metrics([SelectiveRecord("a", True, False, True)])
        result = evaluate_calibration_gate(metrics, metrics)
        self.assertFalse(result["passed"])
        self.assertIn("metric_unavailable:appropriate_abstention_rate", result["reasons"])


if __name__ == "__main__":
    unittest.main()
