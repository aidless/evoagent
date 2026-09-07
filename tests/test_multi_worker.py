import os,subprocess,sys,tempfile,time,unittest
from dataclasses import replace
from pathlib import Path
from evoagent.durable_run import RunState,RunStore
from evoagent.event_log import EventLog
from evoagent.lease import acquire
from evoagent.supervisor import WorkerSupervisor

ROOT=Path(__file__).resolve().parents[1]

class MultiWorkerTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=Path(self.t.name);self.r.joinpath("runs").mkdir(parents=True,exist_ok=True)
 def tearDown(self):self.t.cleanup()
 def test_two_supervisors_only_one_acquires_at_a_time(self):
  store=RunStore(self.r/"runs");store.save(RunState("run-1","agent","goal"))
  a=WorkerSupervisor(store,EventLog(self.r/"a.jsonl"),"worker-A",lease_ttl_s=30)
  b=WorkerSupervisor(store,EventLog(self.r/"b.jsonl"),"worker-B",lease_ttl_s=30)
  out_a=a.run_once(lambda s:replace(s,status="sleeping",next_wakeup_at=1000000),now=100)
  self.assertTrue(out_a["worked"]);self.assertEqual(store.get("run-1").lease_owner,"")
  out_b=b.run_once(lambda s:s,now=120)
  self.assertEqual(out_b,{"worked":False,"reason":"no_eligible_run"})
 def test_takeover_after_timeout_prevents_double_execution(self):
  store=RunStore(self.r/"runs");store.save(acquire(RunState("run-1","agent","goal"),"worker-A",10,100))
  executed=[]
  def step(s):
   if not executed:executed.append(s.run_id)
   return replace(s,status="sleeping",next_wakeup_at=1000000)
  WorkerSupervisor(store,EventLog(self.r/"a.jsonl"),"worker-A",lease_ttl_s=10).run_once(step,now=100)
  WorkerSupervisor(store,EventLog(self.r/"b.jsonl"),"worker-B",lease_ttl_s=30).run_once(step,now=200)
  self.assertEqual(executed,["run-1"])
 def test_subprocess_competition_one_succeeds_one_fails(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);p.joinpath("runs").mkdir(parents=True,exist_ok=True)
   store=RunStore(p/"runs");store.save(RunState("run-2","agent","goal"))
   env={**os.environ,"PYTHONPATH":str(ROOT/"src")}
   (p/"worker.py").write_text(
    "from evoagent.durable_run import RunState,RunStore\n"
    "from evoagent.event_log import EventLog\n"
    "from evoagent.supervisor import WorkerSupervisor\n"
    "from dataclasses import replace\n"
    "import sys\n"
    "from pathlib import Path\n"
    "root=Path(sys.argv[1])\n"
    "owner=sys.argv[2]\n"
    "store=RunStore(root/'runs')\n"
    "out=WorkerSupervisor(store,EventLog(root/(owner+'.jsonl')),owner,lease_ttl_s=30).run_once(lambda s:replace(s,status='sleeping',next_wakeup_at=1000000),now=1000)\n"
    "print(out['status'] if out['worked'] else out['reason'])\n")
   res=[subprocess.run([sys.executable,str(p/"worker.py"),str(p),"worker-"+n],env=env,capture_output=True,text=True) for n in ("A","B","C","D")]
   statuses=[r.stdout.strip() for r in res]
   self.assertEqual(statuses.count("sleeping"),1)
   self.assertEqual(statuses.count("no_eligible_run"),3)
if __name__=="__main__":unittest.main()
