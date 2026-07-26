import json,tempfile,unittest
from pathlib import Path
from evoagent.recovery import RecoveryStrategy,RecoveryRegistry,execute_with_strategy
class RecoveryRegistryTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.r=RecoveryRegistry(self.p/'r.json')
 def tearDown(self):self.t.cleanup()
 def test_register_and_get(self):
  s=RecoveryStrategy(id='strict',status_to_action={'no_evidence':'paper_search_broad'},allowed_actions=frozenset({'paper_search_broad'}),max_replans=1,max_attempts_per_step=1)
  self.r.register(s,'provisional');self.assertEqual(self.r.get('strict')['level'],'provisional')
 def test_audit_returns_registered(self):
  s=RecoveryStrategy(id='s1',status_to_action={'a':'b'},allowed_actions=frozenset({'b'}),max_replans=1,max_attempts_per_step=1);self.r.register(s)
  a=self.r.audit();self.assertEqual(a['strategies'][0]['id'],'s1')
 def test_execute_with_strategy_recovers(self):
  s=RecoveryStrategy(id='recover',status_to_action={'no_evidence':'paper_search_broad'},allowed_actions=frozenset({'paper_search_broad'}),max_replans=1,max_attempts_per_step=2)
  def base(s,c):return __import__('evoagent.workflow',fromlist=['StepResult']).StepResult(s.id,False,status='no_evidence')
  def broad(s,c):return __import__('evoagent.workflow',fromlist=['StepResult']).StepResult(s.id,True,output='ok',status='recovered')
  from evoagent.workflow import Plan,Step
  p=Plan('p','t',(Step('a','base',1),))
  r=execute_with_strategy(p,{'base':base,'paper_search_broad':broad},s)
  self.assertTrue(r.outcome.passed)
 def test_duplicate_id_rejected(self):
  s=RecoveryStrategy(id='dup',status_to_action={'a':'b'},allowed_actions=frozenset({'b'}),max_replans=1,max_attempts_per_step=1)
  self.r.register(s)
  with self.assertRaises(ValueError):self.r.register(s)
if __name__=='__main__':unittest.main()
