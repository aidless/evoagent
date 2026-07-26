import tempfile,unittest
from pathlib import Path
from evoagent.action_policy import ActionPolicy
from evoagent.event_log import EventLog
from evoagent.guarded_executor import GuardedExecutor
from evoagent.idempotency import IdempotencyRegistry
from evoagent.workflow import Plan,Step,StepResult,execute_guarded_plan
from evoagent.workflow_guard import make_guarded_handlers

class WorkflowGuardTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();p=Path(self.t.name);self.guard=GuardedExecutor(ActionPolicy(),IdempotencyRegistry(p/'i.json'),EventLog(p/'e.jsonl'))
 def tearDown(self):self.t.cleanup()
 def test_read_handler_executes_and_reuses(self):
  calls=[];base={'paper_search':lambda s,c:(calls.append(1) or StepResult(s.id,True,['x']))};h=make_guarded_handlers(base,self.guard,'run');a=h['paper_search'](Step('s','paper_search','q'),{});b=h['paper_search'](Step('s','paper_search','q'),{});self.assertTrue(a.passed);self.assertTrue(b.passed);self.assertEqual(len(calls),1)
 def test_model_fallback_requires_approval(self):
  calls=[];base={'model_fallback':lambda s,c:(calls.append(1) or StepResult(s.id,True,'x'))};h=make_guarded_handlers(base,self.guard,'run');r=h['model_fallback'](Step('s','model_fallback','q'),{});self.assertFalse(r.passed);self.assertEqual(r.status,'approval_required');self.assertFalse(calls)
 def test_model_fallback_runs_after_approval(self):
  base={'model_fallback':lambda s,c:StepResult(s.id,True,'x')};h=make_guarded_handlers(base,self.guard,'run',approval_resolver=lambda _:True);self.assertTrue(h['model_fallback'](Step('s','model_fallback','q'),{}).passed)
 def test_missing_manifest_fails_closed(self):
  h=make_guarded_handlers({'unknown':lambda s,c:StepResult(s.id,True)},self.guard,'run');self.assertEqual(h['unknown'](Step('s','unknown','q'),{}).status,'policy_manifest_missing')
 def test_production_entry_rejects_bare_handlers(self):
  plan=Plan('p','t',(Step('s','paper_search','q'),));result=execute_guarded_plan(plan,{'paper_search':lambda s,c:StepResult(s.id,True)});self.assertFalse(result.outcome.passed);self.assertEqual(result.outcome.details['reason'],'unguarded_handlers_rejected')
 def test_production_entry_accepts_guarded_handlers(self):
  plan=Plan('p','t',(Step('s','paper_search','q'),));base={'paper_search':lambda s,c:StepResult(s.id,True,'ok')};handlers=make_guarded_handlers(base,self.guard,'run');result=execute_guarded_plan(plan,handlers);self.assertTrue(result.outcome.passed)

if __name__=='__main__':unittest.main()
