import unittest
from evoagent.protocol import Task
from evoagent.workflow import execute_plan,plan_task
from evoagent.workflow_handlers import make_handlers
from evoagent.recovery import RecoveryPolicy,execute_with_recovery
class WorkflowHandlerTests(unittest.TestCase):
 def test_simple_math_end_to_end(self):
  t=Task('m','auto','Calculate 6 * 7',{'done':True});r=execute_plan(plan_task(t),make_handlers());self.assertTrue(r.outcome.passed);self.assertEqual(r.output,42)
 def test_research_extracts_and_validates(self):
  papers=[{'paper_id':'p1','title':'Verifier Study','abstract':'Verifier Study introduces a verifier for language model reasoning.'}];t=Task('r','auto','Find papers about LLM verifier research.',{'done':True});r=execute_plan(plan_task(t),make_handlers(paper_search=lambda *a:papers));self.assertTrue(r.outcome.passed,r.steps);self.assertIn('[p1]',r.output)
 def test_code_stops_at_sandbox(self):
  t=Task('c','auto','Fix this Python function and run tests.',{'done':True});r=execute_plan(plan_task(t),make_handlers());self.assertFalse(r.outcome.passed);self.assertEqual(r.steps[1].status,'sandbox_required');self.assertEqual(r.steps[2].status,'blocked_by_dependency')
 def test_research_broad_search_recovers(self):
  def search(q,n,y):return [] if n==8 else [{'paper_id':'p1','title':'Broad Evidence','abstract':'Broad Evidence documents language model research.'}]
  t=Task('rb','auto','Find papers about LLM research.',{'done':True});p=plan_task(t);policy=RecoveryPolicy({'no_evidence':'paper_search_broad'},frozenset({'paper_search_broad'}),1,2);r=execute_with_recovery(p,make_handlers(paper_search=search),policy);self.assertTrue(r.outcome.passed,r.steps);self.assertEqual(r.outcome.details['replans_used'],1)
if __name__=='__main__':unittest.main()
