import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from evoagent.workflow import Plan,Step,execute_plan,StepResult
def ok(s,c):return StepResult(s.id,True,output='ok')
class ActiveBundleGate(unittest.TestCase):
 def plan(self):return Plan('p','t',(Step('a','x',1),),bundle_id='bundle-A')
 def test_active_match_allows(self):
  r=execute_plan(self.plan(),{'x':ok},bundle_verifier=lambda x:{'valid':True},active_bundle_resolver=lambda:'bundle-A')
  self.assertTrue(r.outcome.passed)
 def test_active_mismatch_blocks(self):
  r=execute_plan(self.plan(),{'x':ok},bundle_verifier=lambda x:{'valid':True},active_bundle_resolver=lambda:'bundle-B')
  self.assertFalse(r.outcome.passed);self.assertEqual(r.outcome.details['reason'],'plan_bundle_not_active')
 def test_active_resolver_unset_passes(self):
  r=execute_plan(self.plan(),{'x':ok},bundle_verifier=lambda x:{'valid':True})
  self.assertTrue(r.outcome.passed)
 def test_invalid_bundle_blocks_even_with_active_match(self):
  r=execute_plan(self.plan(),{'x':ok},bundle_verifier=lambda x:{'valid':False},active_bundle_resolver=lambda:'bundle-A')
  self.assertFalse(r.outcome.passed);self.assertEqual(r.outcome.details['reason'],'bundle_invalid')
if __name__=='__main__':unittest.main()
