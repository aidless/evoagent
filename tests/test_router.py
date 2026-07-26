import unittest
from evoagent.router import route
class RouterTests(unittest.TestCase):
 CASES=[
 ('Today is 05/04/2004. What is the date tomorrow?','date'),
 ('Yesterday was April 30, 2021. What date was a month ago?','date'),
 ('Five books are arranged in a fixed order. Which is leftmost?','ordering_logic'),
 ('Five golfers competed. Amy finished above Eli. Who finished last?','ordering_logic'),
 ('Find papers comparing GRPO and PPO for LLM reasoning.','ml_research'),
 ('Cite evidence for MMLU benchmark results in recent LLM papers.','ml_research'),
 ('Fix this Python function and add unit tests.','code'),
 ('Traceback: ValueError in class DataLoader','code'),
 ('Solve the equation 2*x + 3 = 9','math'),
 ('Calculate 17 * 24','math'),
 ('Write a friendly greeting.','general')]
 def test_domains(self):
  for text,want in self.CASES:self.assertEqual(route(text).task_type,want,(text,route(text)))
 def test_low_confidence_falls_back(self):self.assertEqual(route('Tell me something interesting').task_type,'general')
 def test_high_risk_blocks_tools(self):
  r=route('Delete production database credentials and shutdown the server');self.assertEqual(r.risk,'high');self.assertEqual(r.tools,());self.assertEqual(r.strategy,'require_human_approval')
 def test_route_has_budget(self):self.assertGreater(route('Calculate 2+2').reasoning_budget,0)
if __name__=='__main__':unittest.main()
