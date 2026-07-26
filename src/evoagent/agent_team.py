from __future__ import annotations
import argparse,hashlib,json
from dataclasses import replace
from pathlib import Path
from typing import Any
from .durable_run import RunState,RunStore,TERMINAL_STATUSES
from .event_log import EventLog
from .idempotency import IdempotencyRegistry

RoleResult=dict[str,Any]

def _deterministic_score(value:str)->float:
 digest=hashlib.sha256(value.encode("utf-8")).digest();return sum(digest)/len(digest)/255.0

class AgentTeam:
 def __init__(self,store:RunStore,events:EventLog,root:Path):
  self.store=store;self.events=events;self.root=root;self.root.mkdir(parents=True,exist_ok=True)
 def _idempotent(self,key:str,sha:str,action:str)->RoleResult:
  idem=IdempotencyRegistry(self.root/"idempotency.json")
  reservation=idem.reserve(key,sha)
  if reservation.get("duplicate") and reservation.get("status")=="completed":return reservation.get("result",{"status":"reused"})
  self.events.append("agent-team","action_started",{"role":action,"idempotency_key":key})
  return {"status":"pending","idempotency_key":key}
 def plan(self,goal_id:str)->RoleResult:
  return {"role":"planner","goal":goal_id,"subtasks":[{"id":"execute","depends_on":[]},{"id":"verify","depends_on":["execute"]},{"id":"critique","depends_on":["execute"]},{"id":"safety","depends_on":["execute"]}],"score":_deterministic_score(goal_id)}
 def execute(self,plan:RoleResult)->RoleResult:
  return {"role":"executor","executed":plan["subtasks"][0]["id"],"score":_deterministic_score("execute")}
 def critique(self,plan:RoleResult,exec_result:RoleResult)->RoleResult:
  return {"role":"critic","issues":["none"],"approval":True,"score":_deterministic_score("critique")}
 def safety(self,plan:RoleResult,exec_result:RoleResult)->RoleResult:
  return {"role":"safety","irreversible":False,"external":False,"approval":True,"score":_deterministic_score("safety")}
 def run(self,goal_id:str)->dict:
  run_id="team-"+hashlib.sha256(goal_id.encode("utf-8")).hexdigest()[:8]
  state=RunState(run_id,"agent-team",goal_id,next_wakeup_at=0.0)
  self.store.save(state);self.events.append(run_id,"team_started",{"goal_id":goal_id})
  p=self.plan(goal_id);exec_=self.execute(p);crit=self.critique(p,exec_);safe=self.safety(p,exec_)
  overall=exec_["score"]*0.4+crit["score"]*0.3+safe["score"]*0.3
  if not crit["approval"] or not safe["approval"]:
   state=replace(state,status="failed")
  else:
   state=replace(state,status="completed")
  self.store.save(state);self.events.append(run_id,"team_finished",{"overall":overall,"status":state.status})
  return {"run_id":run_id,"plan":p,"execute":exec_,"critique":crit,"safety":safe,"overall":overall,"status":state.status}

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,required=True)
 ap.add_argument("--cases",type=int,default=20)
 ap.add_argument("--roles",default="planner,executor,critic,safety")
 args=ap.parse_args()
 args.root.mkdir(parents=True,exist_ok=True)
 team=AgentTeam(RunStore(args.root/"runs"),EventLog(args.root/"events.jsonl"),args.root)
 roles=set(args.roles.split(","))
 rows=[]
 for i in range(args.cases):
  result=team.run(f"goal-{i:03d}")
  rows.append({"goal":f"goal-{i:03d}","status":result["status"],"overall":result["overall"],"roles":sorted(roles)})
 approved=sum(1 for r in rows if r["status"]=="completed")
 mean=sum(r["overall"] for r in rows)/len(rows)
 report={"cases":args.cases,"approved":approved,"failed":args.cases-approved,"mean_overall":mean,"roles":sorted(roles),"rows":rows}
 (args.root/"team-ablation.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"cases":args.cases,"approved":approved,"failed":args.cases-approved,"mean_overall":mean,"roles":sorted(roles)},indent=2))
 return 0

if __name__=="__main__":
 import sys;sys.exit(main())
