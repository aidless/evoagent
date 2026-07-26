from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass,field
from typing import Any
@dataclass(frozen=True)
class Task:
 id:str;domain:str;input:Any;success_criteria:dict[str,Any];allowed_tools:tuple[str,...]=();safety_level:str='normal';metadata:dict[str,Any]=field(default_factory=dict)
 def __post_init__(self):
  if not self.id or not self.domain:raise ValueError('task id/domain required')
  if not self.success_criteria:raise ValueError('success_criteria required')
 def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
@dataclass(frozen=True)
class Outcome:
 task_id:str;passed:bool;score:float;cost:float=0.0;latency_s:float=0.0;safety_violations:int=0;capabilities:dict[str,float]=field(default_factory=dict);details:dict[str,Any]=field(default_factory=dict)
 def __post_init__(self):
  if not 0<=self.score<=1:raise ValueError('score must be in [0,1]')
  if self.cost<0 or self.latency_s<0 or self.safety_violations<0:raise ValueError('metrics cannot be negative')
@dataclass(frozen=True)
class Run:
 run_id:str;candidate_id:str;task_set_hash:str;outcomes:tuple[Outcome,...];model:dict[str,Any]=field(default_factory=dict);config:dict[str,Any]=field(default_factory=dict)
 def by_task(self):
  x={o.task_id:o for o in self.outcomes}
  if len(x)!=len(self.outcomes):raise ValueError('duplicate task_id in run')
  return x
