import unittest
from evoagent.recovery import RecoveryPolicy,execute_with_recovery
from evoagent.workflow import Plan,Step,StepResult
class RecoveryTests(unittest.TestCase):
 def plan(self,action='primary'):return Plan('p','t',(Step('a',action,'x'),))
 def test_fallback_recovers(self):
  h={'primary':lambda s,c:StepResult(s.id,False,status='fallback_required'),'model_fallback':lambda s,c:StepResult(s.id,True,'ok',status='model_fallback')};p=RecoveryPolicy({'fallback_required':'model_fallback'},frozenset({'model_fallback'}),2,2);r=execute_with_recovery(self.plan(),h,p);self.assertTrue(r.outcome.passed);self.assertEqual(r.output,'ok');self.assertEqual(r.steps[0].details['replans_used'],1)
 def test_budget_exhaustion(self):
  h={'primary':lambda s,c:StepResult(s.id,False,status='executor_error')};p=RecoveryPolicy({'executor_error':'retry_same'},frozenset({'retry_same'}),1,3);r=execute_with_recovery(self.plan(),h,p);self.assertFalse(r.outcome.passed);self.assertEqual(len(r.steps[0].details['recovery_trace']),2)
 def test_disallowed_action_not_run(self):
  called=[];h={'primary':lambda s,c:StepResult(s.id,False,status='fallback_required'),'danger':lambda s,c:called.append(1)};p=RecoveryPolicy({'fallback_required':'danger'},frozenset(),2,2);execute_with_recovery(self.plan(),h,p);self.assertFalse(called)
 def test_sandbox_not_bypassed(self):
  called=[];h={'primary':lambda s,c:StepResult(s.id,False,status='sandbox_required'),'model_fallback':lambda s,c:called.append(1)};p=RecoveryPolicy({'sandbox_required':'model_fallback'},frozenset({'model_fallback'}),2,2);r=execute_with_recovery(self.plan(),h,p);self.assertFalse(r.outcome.passed);self.assertFalse(called)
 def test_safety_violation_stops_recovery(self):
  called=[];h={'primary':lambda s,c:StepResult(s.id,False,safety_violations=1,status='executor_error'),'retry':lambda s,c:called.append(1)};p=RecoveryPolicy({'executor_error':'retry'},frozenset({'retry'}),2,2);r=execute_with_recovery(self.plan(),h,p);self.assertEqual(r.outcome.safety_violations,1);self.assertFalse(called)
 def test_human_approval_not_bypassed(self):
  h={'primary':lambda s,c:StepResult(s.id,False,status='human_approval_required'),'model_fallback':lambda s,c:StepResult(s.id,True)};p=RecoveryPolicy({'human_approval_required':'model_fallback'},frozenset({'model_fallback'}),2,2);self.assertFalse(execute_with_recovery(self.plan(),h,p).outcome.passed)
if __name__=='__main__':unittest.main()
