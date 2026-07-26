import json,tempfile,time,unittest
from dataclasses import replace
from pathlib import Path
from evoagent.budget import budget_status,charge
from evoagent.checkpoint import CheckpointStore
from evoagent.durable_run import RunBudget,RunState,RunStore
from evoagent.event_log import EventLog
from evoagent.idempotency import IdempotencyRegistry
from evoagent.lease import acquire,heartbeat
from evoagent.scheduler import DurableScheduler

class DurableRuntimeTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
 def tearDown(self):self.t.cleanup()
 def state(self,**kw):return RunState('run-1','agent','goal',**kw)
 def test_run_store_persists(self):
  s=RunStore(self.root/'runs');s.create(self.state());self.assertEqual(s.get('run-1').goal_id,'goal')
 def test_event_hash_chain_detects_tamper(self):
  log=EventLog(self.root/'events.jsonl');log.append('r','created',{});log.append('r','done',{});self.assertTrue(log.verify()['valid']);rows=log.rows();rows[0]['payload']={'bad':1};(self.root/'events.jsonl').write_text('\n'.join(json.dumps(x) for x in rows)+'\n');self.assertFalse(log.verify()['valid'])
 def test_lease_exclusion_and_takeover(self):
  s=acquire(self.state(),'a',10,now=100)
  with self.assertRaises(RuntimeError):acquire(s,'b',10,now=105)
  taken=acquire(s,'b',10,now=111);self.assertEqual(taken.lease_owner,'b');self.assertGreater(heartbeat(taken,'b',10,now=112).lease_expires_at,112)
 def test_budget_kill_switch(self):
  s=replace(self.state(),budget=RunBudget(max_tool_calls=1));s=charge(s,tool_calls=2);self.assertTrue(budget_status(s)['kill_switch'])
 def test_idempotency_prevents_duplicate(self):
  r=IdempotencyRegistry(self.root/'idem.json');self.assertFalse(r.reserve('k','h')['duplicate']);r.complete('k',{'ok':1});self.assertTrue(r.reserve('k','h')['duplicate']);self.assertEqual(r.get('k')['result'],{'ok':1})
 def test_idempotency_conflict(self):
  r=IdempotencyRegistry(self.root/'idem.json');r.reserve('k','a')
  with self.assertRaises(RuntimeError):r.reserve('k','b')
 def test_checkpoint_integrity(self):
  c=CheckpointStore(self.root/'cp');row=c.create('r',{'step':2});self.assertEqual(c.load(row['checkpoint_id'])['state']['step'],2)
 def test_scheduler_runs_and_releases(self):
  store=RunStore(self.root/'runs');store.create(self.state());log=EventLog(self.root/'events.jsonl');scheduler=DurableScheduler(store,log,'worker')
  out=scheduler.run_once(lambda s:replace(s,status='sleeping',next_wakeup_at=time.time()+60));self.assertTrue(out['worked']);self.assertEqual(store.get('run-1').lease_owner,'');self.assertTrue(log.verify()['valid'])
 def test_scheduler_blocks_on_handler_crash(self):
  store=RunStore(self.root/'runs');store.create(self.state());scheduler=DurableScheduler(store,EventLog(self.root/'events.jsonl'),'worker')
  out=scheduler.run_once(lambda _:(_ for _ in ()).throw(RuntimeError('boom')));self.assertEqual(out['status'],'blocked');self.assertIn('boom',store.get('run-1').metadata['last_error'])
 def test_100_crash_points_never_duplicate_side_effect(self):
  for point in range(100):
   registry=IdempotencyRegistry(self.root/f'idem-{point}.json');effects=[];key=f'action-{point}';digest=f'hash-{point}'
   phase=point%3
   if phase==0:
    pass
   else:
    registry.reserve(key,digest)
    if phase==2:effects.append(key)
   row=registry.get(key)
   if row is None:
    registry.reserve(key,digest);effects.append(key);registry.complete(key,{'ok':True})
   elif row['status']=='reserved':
    registry.resolve(key,performed=(key in effects),result={'ok':True} if key in effects else None)
    if registry.get(key) is None:
     registry.reserve(key,digest);effects.append(key);registry.complete(key,{'ok':True})
   self.assertEqual(effects.count(key),1)
   self.assertEqual(registry.get(key)['status'],'completed')

if __name__=='__main__':unittest.main()
