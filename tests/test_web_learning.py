import tempfile
import unittest
from pathlib import Path

from evoagent.web_learning import Paper, WebKnowledgeStore, derive_lessons, parse_arxiv_feed, relevance

FEED = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry>
  <id>http://arxiv.org/abs/2401.00001v2</id>
  <updated>2026-01-01T00:00:00Z</updated><published>2024-01-01T00:00:00Z</published>
  <title>Reflective Self-Improving Language Agents</title>
  <summary>Language model agents use reflection, benchmark evaluation, and safety gates to improve.</summary>
  <author><name>Alice Example</name></author><category term="cs.AI" />
 </entry>
</feed>'''


class WebLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "knowledge.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_parse_arxiv_feed(self):
        papers = parse_arxiv_feed(FEED)
        self.assertEqual(papers[0].paper_id, "2401.00001")
        self.assertEqual(papers[0].authors, ("Alice Example",))
        self.assertEqual(papers[0].categories, ("cs.AI",))

    def test_relevance_and_lessons(self):
        paper = parse_arxiv_feed(FEED)[0]
        self.assertGreaterEqual(relevance(paper), 0.5)
        lessons = derive_lessons(paper)
        self.assertTrue(any("feedback" in lesson for lesson in lessons))
        self.assertTrue(any("safety" in lesson.lower() for lesson in lessons))

    def test_store_deduplicates_and_never_auto_activates(self):
        store = WebKnowledgeStore(self.path)
        paper = parse_arxiv_feed(FEED)[0]
        first = store.ingest([paper], "r1")
        second = store.ingest([paper], "r2")
        self.assertEqual(first["added"], 1)
        self.assertEqual(second["added"], 0)
        reloaded = WebKnowledgeStore(self.path)
        self.assertFalse(reloaded.data["cards"][0]["trust"]["automatic_activation"])
        self.assertEqual(reloaded.digest()["sources"], 1)



    def test_interface_paper_yields_interface_design_lesson(self):
        paper = Paper(
            "x",
            "Agent-Computer Interfaces",
            "We study tool use and interface design for language model agents.",
            "2024",
            "2024",
            ("A",),
            ("cs.AI",),
            "https://arxiv.org/abs/x",
        )
        self.assertTrue(any("interfaces" in item for item in derive_lessons(paper)))


    def test_tool_and_reasoning_papers_yield_guarded_lessons(self):
        tool = Paper(
            "tool",
            "Toolformer",
            "A language model learns tool use and external tools.",
            "2023",
            "2023",
            ("A",),
            ("cs.CL",),
            "https://arxiv.org/abs/tool",
        )
        reasoning = Paper(
            "star",
            "STaR: Bootstrapping Reasoning With Reasoning",
            "A self-taught reasoner bootstraps from generated rationale traces.",
            "2022",
            "2022",
            ("B",),
            ("cs.AI",),
            "https://arxiv.org/abs/star",
        )
        self.assertTrue(any("invocation correctness" in item for item in derive_lessons(tool)))
        self.assertTrue(any("answer verification" in item for item in derive_lessons(reasoning)))

if __name__ == "__main__":
    unittest.main()
