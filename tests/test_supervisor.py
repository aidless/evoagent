import tempfile,time,unittest
from dataclasses import replace
from pathlib import Path
from evoagent.budget import charge
from evoagent.durable_run import RunBudget,RunState,RunStore
from evoagent.event_log import EventLog
from evoagent.lease import acquire
from evoagent.supervisor import WorkerSupervisor

class SupervisorTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=Path(self.t.name);self.store=RunStore(self.r/"runs");self.log=EventLog(self.r/"events.jsonl")
 def tearDown(self):self.t.cleanup()
 def make(self,state=None,lease_owner="",ttl=10,now=100,**kwargs):s=state or RunState("run-1","agent","goal",**kwargs);return self.store.save(acquire(s,lease_owner or "alice",ttl,now))
 def test_takeover_after_lease_timeout(self):
  self.make();sup=WorkerSupervisor(self.store,self.log,"bob",lease_ttl_s=30)
  taken=sup.heartbeat(now=120);self.assertEqual(taken[0].lease_owner,"bob");self.assertEqual(self.store.get("run-1").lease_owner,"bob");self.assertTrue(self.log.verify()["valid"])
 def test_active_lease_is_not_taken(self):
  self.make(lease_owner="alice",ttl=200,now=100);sup=WorkerSupervisor(self.store,self.log,"bob",lease_ttl_s=30);self.assertEqual(sup.heartbeat(now=120),[]);self.assertEqual(self.store.get("run-1").lease_owner,"alice")
 def test_owner_heartbeat_renews_lease(self):
  self.make(lease_owner="bob",ttl=200,now=100);sup=WorkerSupervisor(self.store,self.log,"bob",lease_ttl_s=300);out=sup.run_once(lambda s:replace(s,status="sleeping",next_wakeup_at=1000000),now=120);self.assertTrue(out["worked"]);self.assertEqual(self.store.get("run-1").lease_owner,"")
 def test_blocked_run_is_not_picked(self):
  self.make();self.store.save(replace(self.store.get("run-1"),status="blocked"));self.assertEqual(WorkerSupervisor(self.store,self.log,"bob").run_once(lambda s:s),{"worked":False,"reason":"no_eligible_run"})
 def test_kill_switch_prevents_next_step(self):
  s=self.make(budget=RunBudget(max_tool_calls=1));self.store.save(charge(s,tool_calls=2));out=WorkerSupervisor(self.store,self.log,"bob").run_once(lambda s:s);self.assertEqual(out["status"],"failed")
 def test_recovery_after_crash_does_not_duplicate_side_effects(self):
  s=self.make(lease_owner="alice",ttl=60,now=100);self.store.save(s)
  idem_file=self.r/"idempotency.json";from evoagent.idempotency import IdempotencyRegistry
  def step(state):
   idem=IdempotencyRegistry(idem_file)
   if idem.get("effect-1") is None:idem.reserve("effect-1","h")
   (self.r/"effects.jsonl").write_text("effect-1\n")
   idem.complete("effect-1",{"ok":True})
   return replace(state,status="sleeping",next_wakeup_at=time.time()+3600)
  WorkerSupervisor(self.store,self.log,"alice",lease_ttl_s=60).run_once(step,now=100)
  WorkerSupervisor(self.store,self.log,"bob",lease_ttl_s=30).run_once(step,now=200)
  self.assertEqual((self.r/"effects.jsonl").read_text().count("effect-1"),1)
if __name__=="__main__":unittest.main()
