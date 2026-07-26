import unittest
from evoagent.protocol import Task
from evoagent.workflow import Plan,Step,StepResult,execute_plan,plan_task
class WorkflowTests(unittest.TestCase):
 def ok(self,s,c):return StepResult(s.id,True,output=s.id,cost=1)
 def test_research_plan_is_dag(self):
  p=plan_task(Task('1','auto','Find papers and cite evidence about LLM evaluation.',{'done':True}));self.assertEqual([x.id for x in p.order()],['retrieve','synthesize','verify'])
 def test_multistep_success(self):
  p=Plan('p','t',(Step('a','x',1),Step('b','x',2,('a',))));r=execute_plan(p,{'x':self.ok});self.assertTrue(r.outcome.passed);self.assertEqual(r.outcome.cost,2);self.assertEqual(r.output,'b')
 def test_failure_blocks_downstream(self):
  p=Plan('p','t',(Step('a','bad',1),Step('b','x',2,('a',))));r=execute_plan(p,{'bad':lambda s,c:StepResult(s.id,False),'x':self.ok});self.assertFalse(r.outcome.passed);self.assertEqual(r.steps[1].status,'blocked_by_dependency')
 def test_cycle_rejected(self):
  p=Plan('p','t',(Step('a','x',1,('b',)),Step('b','x',2,('a',))))
  with self.assertRaisesRegex(ValueError,'cycle'):p.order()
 def test_missing_dependency_rejected(self):
  with self.assertRaisesRegex(ValueError,'invalid dependency'):Plan('p','t',(Step('a','x',1,('z',)),)).order()
 def test_step_budget(self):
  with self.assertRaisesRegex(ValueError,'budget'):Plan('p','t',tuple(Step(str(i),'x',i) for i in range(4)),max_steps=3).order()
 def test_missing_executor_fails_closed(self):
  r=execute_plan(Plan('p','t',(Step('a','none',1),)),{});self.assertEqual(r.steps[0].status,'executor_unavailable')
 def test_safety_aggregates(self):
  r=execute_plan(Plan('p','t',(Step('a','x',1),)),{'x':lambda s,c:StepResult(s.id,True,safety_violations=1)});self.assertEqual(r.outcome.safety_violations,1)
 def test_invalid_bundle_blocks_execution(self):
  called=[];p=Plan('p','t',(Step('a','x',1),),bundle_id='bad');r=execute_plan(p,{'x':lambda s,c:called.append(1)},bundle_verifier=lambda x:{'valid':False});self.assertFalse(r.outcome.passed);self.assertFalse(called);self.assertEqual(r.outcome.details['reason'],'bundle_invalid')
if __name__=='__main__':unittest.main()
