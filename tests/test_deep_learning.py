import tempfile
import unittest
from pathlib import Path

from evoagent.deep_learning import build_deep_digest, build_evidence_map
from evoagent.web_learning import Paper, WebKnowledgeStore


class DeepLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WebKnowledgeStore(Path(self.temp.name) / "web.json")
        papers = [
            Paper("1", "Tree of Thoughts", "Tree search improves planning.", "2023", "2023", ("A",), ("cs.AI",), "u1"),
            Paper("2", "Toolformer", "Language models learn tool use.", "2023", "2023", ("B",), ("cs.CL",), "u2"),
            Paper("3", "Eureka Reward Design", "Models generate reward functions.", "2023", "2023", ("C",), ("cs.AI",), "u3"),
            Paper("4", "SWE-bench", "A real-world software engineering benchmark from GitHub issues.", "2023", "2023", ("D",), ("cs.SE",), "u4"),
        ]
        self.store.ingest(papers, "run", min_relevance=0)

    def tearDown(self):
        self.temp.cleanup()

    def test_evidence_map_links_sources_and_components(self):
        evidence = build_evidence_map(self.store)
        by_id = {x["claim_id"]: x for x in evidence["claims"]}
        self.assertEqual(by_id["search_and_planning"]["sources"], ["arxiv:1"])
        self.assertIn("autonomy.py", by_id["search_and_planning"]["components"])
        self.assertFalse(by_id["search_and_planning"]["automatic_activation"])

    def test_digest_is_provenance_bound_and_has_limitations(self):
        digest = build_deep_digest(self.store)
        self.assertEqual(len(digest["provenance_sha256"]), 64)
        self.assertTrue(digest["limitations"])
        self.assertTrue(all(x["gate"] == "proposal_only_until_benchmark_passes" for x in digest["recommendations"]))



    def test_extended_assurance_areas_report_evidence_gaps(self):
        evidence = build_evidence_map(self.store)
        by_id = {x["claim_id"]: x for x in evidence["claims"]}
        self.assertIn("uncertainty_and_abstention", by_id)
        self.assertEqual(by_id["uncertainty_and_abstention"]["status"], "gap")
        self.assertIn("contamination_control", evidence["coverage"]["gaps"])
        self.assertEqual(by_id["latent_risk"]["automatic_activation"], False)

if __name__ == "__main__":
    unittest.main()
