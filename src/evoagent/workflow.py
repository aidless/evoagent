from __future__ import annotations
import time
from dataclasses import dataclass,field
from typing import Any,Callable
from .protocol import Outcome,Task
from .router import route
@dataclass(frozen=True)
class Step:
 id:str;action:str;input:Any;depends_on:tuple[str,...]=();required:bool=True;validator:str='passed'
@dataclass(frozen=True)
class Plan:
 id:str;task_id:str;steps:tuple[Step,...];max_steps:int=12;bundle_id:str=''
 def order(self):
  if len(self.steps)>self.max_steps:raise ValueError('step budget exceeded')
  by={s.id:s for s in self.steps}
  if len(by)!=len(self.steps):raise ValueError('duplicate step id')
  for s in self.steps:
   if s.id in s.depends_on or any(d not in by for d in s.depends_on):raise ValueError('invalid dependency')
  state={};out=[]
  def visit(x):
   if state.get(x)==1:raise ValueError('cycle detected')
   if state.get(x)==2:return
   state[x]=1
   for d in by[x].depends_on:visit(d)
   state[x]=2;out.append(by[x])
  for x in by:visit(x)
  return tuple(out)
@dataclass(frozen=True)
class StepResult:
 step_id:str;passed:bool;output:Any=None;cost:float=0;latency_s:float=0;safety_violations:int=0;status:str='completed';details:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class WorkflowResult:
 plan:Plan;steps:tuple[StepResult,...];outcome:Outcome;output:Any

def plan_task(task:Task)->Plan:
 text=task.input if isinstance(task.input,str) else str(task.input);r=route(text)
 if r.risk=='high':steps=(Step('approval','human_approval',text),)
 elif r.task_type=='ml_research':steps=(Step('retrieve','paper_search',text),Step('synthesize','research_synthesis',text,('retrieve',)),Step('verify','claim_validation',text,('synthesize',)))
 elif r.task_type=='code':steps=(Step('analyze','code_analysis',text),Step('execute','code_sandbox',text,('analyze',)),Step('test','unit_tests',text,('execute',)))
 else:steps=(Step('solve','dispatch',text),)
 return Plan('plan-'+task.id,task.id,steps)
def execute_plan(plan:Plan,handlers:dict[str,Callable[[Step,dict[str,StepResult]],StepResult]],bundle_verifier=None,active_bundle_resolver=None,require_guarded_handlers:bool=False)->WorkflowResult:
 started=time.monotonic()
 if require_guarded_handlers and not getattr(handlers,"guarded",False):
  out=Outcome(plan.task_id,False,0.0,0.0,time.monotonic()-started,0,{"workflow":0.0},{"plan_id":plan.id,"reason":"unguarded_handlers_rejected"})
  return WorkflowResult(plan,(),out,None)
 if plan.bundle_id and (not bundle_verifier or not bundle_verifier(plan.bundle_id).get('valid')):
  out=Outcome(plan.task_id,False,0.0,0.0,time.monotonic()-started,0,{'workflow':0.0},{'plan_id':plan.id,'bundle_id':plan.bundle_id,'reason':'bundle_invalid'})
  return WorkflowResult(plan,(),out,None)
 if active_bundle_resolver and plan.bundle_id:
  active=active_bundle_resolver()
  if active and active!=plan.bundle_id:
   out=Outcome(plan.task_id,False,0.0,0.0,time.monotonic()-started,0,{'workflow':0.0},{'plan_id':plan.id,'bundle_id':plan.bundle_id,'active_bundle':active,'reason':'plan_bundle_not_active'})
   return WorkflowResult(plan,(),out,None)
 results={}
 for step in plan.order():
  if any(not results[d].passed for d in step.depends_on):results[step.id]=StepResult(step.id,False,status='blocked_by_dependency');continue
  h=handlers.get(step.action)
  if not h:results[step.id]=StepResult(step.id,False,status='executor_unavailable');continue
  t=time.monotonic()
  try:r=h(step,results);r=StepResult(r.step_id,r.passed,r.output,r.cost,r.latency_s or time.monotonic()-t,r.safety_violations,r.status,r.details)
  except Exception as e:r=StepResult(step.id,False,status='executor_error',details={'error':f'{type(e).__name__}: {e}'},latency_s=time.monotonic()-t)
  if r.step_id!=step.id:raise ValueError('handler returned wrong step id')
  results[step.id]=r
 ordered=tuple(results[s.id] for s in plan.order());required=[results[s.id] for s in plan.steps if s.required];passed=bool(required) and all(x.passed for x in required);safety=sum(x.safety_violations for x in ordered);cost=sum(x.cost for x in ordered);output=next((x.output for x in reversed(ordered) if x.passed and x.output is not None),None);out=Outcome(plan.task_id,passed,1.0 if passed else 0.0,cost,time.monotonic()-started,safety,{'workflow':1.0 if passed else 0.0},{'plan_id':plan.id,'bundle_id':plan.bundle_id or None,'step_status':{x.step_id:x.status for x in ordered}});return WorkflowResult(plan,ordered,out,output)


def execute_guarded_plan(plan:Plan,handlers:dict[str,Callable[[Step,dict[str,StepResult]],StepResult]],bundle_verifier=None,active_bundle_resolver=None)->WorkflowResult:
 return execute_plan(plan,handlers,bundle_verifier,active_bundle_resolver,require_guarded_handlers=True)
