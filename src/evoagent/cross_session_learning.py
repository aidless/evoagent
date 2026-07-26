from __future__ import annotations
import argparse,hashlib,json
from dataclasses import dataclass,field
from pathlib import Path
from typing import Any

@dataclass
class Experience:
 trajectory_id:str
 task_type:str
 strategy_id:str
 outcome:str
 reward:float
 failure_class:str=""
 safety_violations:int=0
 verified:bool=False
 metadata:dict[str,Any]=field(default_factory=dict)
 def fingerprint(self)->str:
  base={"trajectory":self.trajectory_id,"task_type":self.task_type,"strategy":self.strategy_id,"outcome":self.outcome,"reward":self.reward,"failure":self.failure_class,"safety":self.safety_violations,"verified":self.verified}
  return hashlib.sha256(json.dumps(base,sort_keys=True).encode("utf-8")).hexdigest()[:16]

class ExperienceStore:
 def __init__(self,path:Path):
  self.path=path
  if path.exists():self.data=json.loads(path.read_text(encoding="utf-8-sig"))
  else:self.data={"experiences":[]}
 def add(self,experience:Experience)->dict:
  existing=next((x for x in self.data["experiences"] if x["fingerprint"]==experience.fingerprint()),None)
  if existing:
   existing["count"]=existing.get("count",1)+1
   return {"fingerprint":experience.fingerprint(),"deduplicated":True}
  row={"fingerprint":experience.fingerprint(),"trajectory_id":experience.trajectory_id,"task_type":experience.task_type,"strategy_id":experience.strategy_id,"outcome":experience.outcome,"reward":experience.reward,"failure_class":experience.failure_class,"safety_violations":experience.safety_violations,"verified":experience.verified,"metadata":experience.metadata,"count":1}
  self.data["experiences"].append(row);return row
 def save(self)->None:
  self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps(self.data,indent=2)+"\n",encoding="utf-8")
 def recall(self,task_type:str,top_k:int=3,verified_only:bool=True)->list[dict]:
  rows=[x for x in self.data["experiences"] if x["task_type"]==task_type and (not verified_only or x["verified"])]
  rows.sort(key=lambda x:(-x["reward"],-x.get("count",1)))
  return rows[:top_k]
 def verified_rate(self)->float:
  if not self.data["experiences"]:return 0.0
  verified=sum(1 for x in self.data["experiences"] if x["verified"])
  return verified/len(self.data["experiences"])
 def safety_violations(self)->int:
  return sum(x["safety_violations"] for x in self.data["experiences"])

class SkillCandidate:
 def __init__(self,store:ExperienceStore,min_runs:int=3,min_reward:float=0.7):
  self.store=store;self.min_runs=min_runs;self.min_reward=min_reward
 def propose(self,strategy_id:str,reward:float,runs:int)->dict:
  if runs<self.min_runs:return {"candidate":strategy_id,"promoted":False,"reason":"insufficient_runs"}
  if reward<self.min_reward:return {"candidate":strategy_id,"promoted":False,"reason":"reward_below_threshold"}
  return {"candidate":strategy_id,"promoted":True,"runs":runs,"reward":reward,"shadow_checked":False,"development_passed":False,"hidden_confirmed":False,"trigger_safe":False}

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,required=True)
 ap.add_argument("--case",type=int,default=10)
 args=ap.parse_args()
 args.root.mkdir(parents=True,exist_ok=True)
 store=ExperienceStore(args.root/"experiences.json")
 summary={"rounds":args.case,"added":0,"deduplicated":0,"verified":0,"total_reward":0.0,"safety_violations":0}
 for i in range(args.case):
  exp=Experience(trajectory_id=f"t-{i:03d}",task_type="agent_team" if i%2==0 else "single_agent",strategy_id="candidate-A" if i%2==0 else "candidate-B",outcome="completed" if i%3!=0 else "failed",reward=0.8 if i%3!=0 else 0.2,verified=i%4!=0,safety_violations=1 if i%7==0 else 0)
  result=store.add(exp)
  summary["added"]+=0 if result.get("deduplicated") else 1
  summary["deduplicated"]+=1 if result.get("deduplicated") else 0
  summary["verified"]+=1 if exp.verified else 0
  summary["total_reward"]+=exp.reward
  summary["safety_violations"]+=exp.safety_violations
  store.save()
  if i%5==0:
   recall=store.recall("agent_team" if i%2==0 else "single_agent")
   candidate=SkillCandidate(store).propose("candidate-A",sum(x["reward"] for x in store.data["experiences"])/len(store.data["experiences"]),len(store.data["experiences"]))
 summary["verified_rate"]=store.verified_rate()
 summary["recall_agent_team"]=store.recall("agent_team")
 summary["recall_single_agent"]=store.recall("single_agent")
 (args.root/"learning-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("recall_agent_team","recall_single_agent")},indent=2))
 return 0

if __name__=="__main__":
 import sys;sys.exit(main())
