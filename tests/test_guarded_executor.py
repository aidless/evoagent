import tempfile,unittest
from pathlib import Path
from evoagent.action_policy import ActionPolicy,ActionRequest
from evoagent.event_log import EventLog
from evoagent.guarded_executor import GuardedExecutor
from evoagent.idempotency import IdempotencyRegistry

class GuardedExecutorTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();p=Path(self.t.name);self.log=EventLog(p/'events.jsonl');self.g=GuardedExecutor(ActionPolicy(allowed_write_roots=('E:\\workspace',)),IdempotencyRegistry(p/'idem.json'),self.log)
 def tearDown(self):self.t.cleanup()
 def test_deny_never_executes(self):
  calls=[];r=self.g.execute('r',ActionRequest('a','write_file',{'promotion_gate':False},filesystem_scope=('E:\\workspace\\x',)),'k',lambda:calls.append(1));self.assertEqual(r['status'],'denied');self.assertFalse(calls)
 def test_approval_gate(self):
  calls=[];req=ActionRequest('a','send_email',{'to':'x'});r=self.g.execute('r',req,'k',lambda:calls.append(1));self.assertEqual(r['status'],'approval_required');self.assertFalse(calls)
 def test_completed_action_reused(self):
  calls=[];req=ActionRequest('a','write_file',{'path':'x'},filesystem_scope=('E:\\workspace\\x',));fn=lambda:(calls.append(1) or {'ok':True});a=self.g.execute('r',req,'k',fn);b=self.g.execute('r',req,'k',fn);self.assertEqual(a['status'],'completed');self.assertEqual(b['status'],'reused');self.assertEqual(len(calls),1);self.assertTrue(self.log.verify()['valid'])
 def test_failed_action_is_not_blindly_retried(self):
  req=ActionRequest('a','write_file',{'path':'x'},filesystem_scope=('E:\\workspace\\x',));a=self.g.execute('r',req,'k',lambda:(_ for _ in ()).throw(RuntimeError('boom')));b=self.g.execute('r',req,'k',lambda:1);self.assertEqual(a['status'],'uncertain_prior_attempt');self.assertEqual(b['status'],'uncertain_prior_attempt');self.assertFalse(b['executed'])
if __name__=='__main__':unittest.main()
