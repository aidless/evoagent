from pathlib import Path
import unittest
from evoagent.action_policy import ActionPolicy,ActionRequest,PolicyEffect,RiskLevel
from evoagent.action_safety_benchmark import evaluate_action_safety

class ActionPolicyTests(unittest.TestCase):
 def test_read_only_allowed(self):
  r=ActionPolicy().evaluate(ActionRequest('a','read_file',{'path':'x'}));self.assertEqual(r.effect,PolicyEffect.ALLOW);self.assertEqual(r.risk,RiskLevel.READ_ONLY)
 def test_workspace_write_scoped(self):
  p=ActionPolicy(allowed_write_roots=('E:\\workspace',));r=p.evaluate(ActionRequest('a','write_file',{'path':'E:\\workspace\\x'},filesystem_scope=('E:\\workspace\\x',)));self.assertEqual(r.effect,PolicyEffect.ALLOW)
 def test_outside_write_denied(self):
  p=ActionPolicy(allowed_write_roots=('E:\\workspace',));r=p.evaluate(ActionRequest('a','write_file',{},filesystem_scope=('C:\\Windows\\x',)));self.assertEqual(r.effect,PolicyEffect.DENY)
 def test_external_requires_approval(self):
  r=ActionPolicy().evaluate(ActionRequest('a','send_email',{'to':'x'}));self.assertEqual(r.effect,PolicyEffect.APPROVE);self.assertTrue(r.requires_approval)
 def test_trust_root_change_denied(self):
  r=ActionPolicy().evaluate(ActionRequest('a','write_file',{'promotion_gate':False},filesystem_scope=('E:\\x',)));self.assertEqual(r.effect,PolicyEffect.DENY);self.assertEqual(r.risk,RiskLevel.TRUST_ROOT_CHANGE)
 def test_privilege_bypass_denied(self):
  r=ActionPolicy().evaluate(ActionRequest('a','shell',{'cmd':'disable safety gate'}));self.assertEqual(r.effect,PolicyEffect.DENY)
 def test_destructive_requires_approval(self):
  r=ActionPolicy().evaluate(ActionRequest('a','shell',{'cmd':'Remove-Item x -Recurse'},reversible=False));self.assertEqual(r.effect,PolicyEffect.APPROVE);self.assertEqual(r.risk,RiskLevel.IRREVERSIBLE)
 def test_prefix_collision_is_outside_root(self):
  p=ActionPolicy(allowed_write_roots=('E:\\workspace',));r=p.evaluate(ActionRequest('a','write_file',{},filesystem_scope=('E:\\workspace-evil\\x',)));self.assertEqual(r.effect,PolicyEffect.DENY)

 def test_real_45_action_safety_tasks_have_zero_violations(self):
  project=Path(__file__).resolve().parents[1];private=project.parent/f'{project.name}-private'/'benchmark-registry-v2';result=evaluate_action_safety(private/'tasks.json',private/'answer-key.json');self.assertEqual(result['n'],45);self.assertEqual(result['safety_violations'],0);self.assertEqual(result['passed'],45)

if __name__=='__main__':unittest.main()
