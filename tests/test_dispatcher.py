import unittest
from pathlib import Path
from evoagent.dispatcher import dispatch,safe_calculate
from evoagent.protocol import Task
from evoagent.skill_registry import SkillRegistry,SkillSpec
class DispatcherTests(unittest.TestCase):
 def task(self,i,text):return Task(str(i),'auto',text,{'completed':True})
 def test_math(self):
  r=dispatch(self.task(1,'Calculate 17 * 24'));self.assertTrue(r.outcome.passed);self.assertEqual(r.output,408)
 def test_math_blocks_code(self):
  with self.assertRaises(ValueError):safe_calculate("__import__('os').system('x')")
 def test_date(self):
  q='Today is 05/04/2004. What is the date tomorrow?\nOptions:\n(A) 05/04/2004\n(B) 05/05/2004';r=dispatch(self.task(2,q));self.assertEqual(r.output,'B')
 def test_logic(self):
  q='Five competitors have distinct finishing ranks. amber finished above birch. birch finished above cedar. cedar finished above denim. denim finished above elm.\nOptions:\n(A) amber finished first\n(B) birch finished first\n(C) cedar finished first\n(D) denim finished first\n(E) elm finished first';r=dispatch(self.task(3,q));self.assertEqual(r.output,'A')
 def test_research_uses_injected_search(self):
  r=dispatch(self.task(4,'Find papers about LLM benchmark evaluation.'),paper_search=lambda *a:[{'paper_id':'p1'}]);self.assertTrue(r.outcome.passed);self.assertEqual(r.output['evidence'][0]['paper_id'],'p1')
 def test_code_fails_closed_without_sandbox(self):self.assertEqual(dispatch(self.task(5,'Fix this Python function.')).status,'sandbox_required')
 def test_high_risk_requires_approval(self):self.assertEqual(dispatch(self.task(6,'Delete production database password.')).status,'human_approval_required')
 def test_general_fallback(self):
  r=dispatch(self.task(7,'Write a greeting.'),model_fallback=lambda t,r:{'passed':True,'output':'hello'});self.assertEqual(r.output,'hello')
 def test_dispatch_records_active_skill(self):
  import tempfile
  with tempfile.TemporaryDirectory() as td:
   reg=SkillRegistry(Path(td)/'s.json');reg.register(SkillSpec('calc','1','math','x',{}, {},('local_compute',),'normal','provisional',{}));reg.activate('calc@1');r=dispatch(self.task(8,'Calculate 2+2'),skill_registry=reg);self.assertEqual(r.outcome.details['skill_id'],'calc@1')
 def test_missing_skill_fails_closed_when_registry_supplied(self):
  import tempfile
  with tempfile.TemporaryDirectory() as td:self.assertEqual(dispatch(self.task(9,'Calculate 2+2'),skill_registry=SkillRegistry(Path(td)/'s.json')).status,'skill_unavailable')
if __name__=='__main__':unittest.main()

