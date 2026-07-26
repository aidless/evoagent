import json
import tempfile
import unittest
from pathlib import Path

from evoagent.core import save_json
from evoagent.research_harvest import _abstract, summarize
from evoagent.research_synthesis import synthesize


class ResearchHundredTests(unittest.TestCase):
    def test_openalex_abstract_reconstruction(self):
        self.assertEqual(_abstract({"agent": [1], "an": [0], "learns": [2]}), "an agent learns")

    def test_summary_reports_supply_chain_isolation(self):
        summary = summarize([{"title": "Agent benchmark", "abstract": "tool safety"}], [{"status": "downloaded", "bytes": 3, "language": "Python", "license": "MIT"}])
        self.assertEqual(summary["repositories_downloaded"], 1)
        self.assertIn("no repository code executed", summary["supply_chain_policy"])

    def test_synthesis_cross_links_papers_and_repositories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); base = root / ".evo" / "research-100x100"; repo = base / "repositories" / "x__y"; repo.mkdir(parents=True)
            (repo / "README.md").write_text("Agent memory, tool use, safety benchmark", encoding="utf-8")
            save_json(base / "papers.json", {"papers": [{"work_id": "W1", "title": "Agent memory", "abstract": "tool safety benchmark"}]})
            save_json(base / "repositories.json", {"repositories": [{"full_name": "x/y", "description": "agent", "path": str(repo), "bytes": 1, "executed": False}]})
            result = synthesize(root)
            self.assertEqual(result["corpus"]["repositories_executed"], 0)
            self.assertTrue(any(x["topic"] == "memory" and x["paper_support"] == 1 and x["repository_support"] == 1 for x in result["cross_evidence"]))


if __name__ == "__main__":
    unittest.main()
