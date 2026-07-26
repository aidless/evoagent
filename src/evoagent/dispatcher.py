from __future__ import annotations
import ast,operator,re,time
from dataclasses import dataclass
from typing import Any,Callable
from .protocol import Outcome,Task
from .reasoning_tools import solve_date,solve_logic
from .router import Route,route
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow,ast.USub:operator.neg,ast.UAdd:operator.pos}
def safe_calculate(expr:str):
 tree=ast.parse(expr,mode='eval')
 def ev(n,depth=0):
  if depth>12:raise ValueError('expression too deep')
  if isinstance(n,ast.Expression):return ev(n.body,depth+1)
  if isinstance(n,ast.Constant) and type(n.value) in (int,float):return n.value
  if isinstance(n,ast.BinOp) and type(n.op) in OPS:
   a,b=ev(n.left,depth+1),ev(n.right,depth+1)
   if isinstance(n.op,ast.Pow) and (abs(b)>10 or abs(a)>1e6):raise ValueError('power limit')
   return OPS[type(n.op)](a,b)
  if isinstance(n,ast.UnaryOp) and type(n.op) in OPS:return OPS[type(n.op)](ev(n.operand,depth+1))
  raise ValueError('unsupported expression')
 v=ev(tree)
 if not isinstance(v,(int,float)) or abs(v)>1e15:raise ValueError('result limit')
 return v
def extract_expression(text):
 m=re.search(r'(?:calculate|compute)\s+([0-9eE.()+\-*/%^ ]+)',text,re.I);return m.group(1).strip().replace('^','**') if m else None
@dataclass(frozen=True)
class DispatchResult:
 route:Route;outcome:Outcome;output:Any;status:str

def dispatch(task:Task,model_fallback:Callable[[str,Route],dict]|None=None,paper_search:Callable[...,list]|None=None,skill_registry=None)->DispatchResult:
 text=task.input if isinstance(task.input,str) else str(task.input.get('text') or task.input.get('question') or task.input);r=route(text);started=time.monotonic();output=None;passed=False;status='failed_closed';details={'route':r.as_dict()};active_skill=skill_registry.resolve(r.task_type) if skill_registry else None
 if active_skill: details['skill_id']=active_skill['name']+'@'+active_skill['version']
 caps={r.task_type:0.0}
 try:
  if skill_registry and r.task_type in ('date','ordering_logic','math','ml_research') and not active_skill: status='skill_unavailable'
  elif r.risk=='high':status='human_approval_required';details['reason']='high_risk'
  elif r.task_type=='date':output=solve_date(text);passed=output is not None;status='tool_success' if passed else 'fallback_required'
  elif r.task_type=='ordering_logic':output=solve_logic(text);passed=output is not None;status='tool_success' if passed else 'fallback_required'
  elif r.task_type=='math':
   expr=extract_expression(text)
   if expr is not None:output=safe_calculate(expr);passed=True;status='tool_success'
   else:status='fallback_required'
  elif r.task_type=='ml_research':
   if paper_search is None:
    from .knowledge import search as paper_search
   rows=paper_search(text,8,2024);output={'evidence':rows};passed=bool(rows);status='evidence_collected' if passed else 'no_evidence'
  elif r.task_type=='code':status='sandbox_required';details['reason']='os_sandbox_not_configured'
  elif model_fallback:
   x=model_fallback(text,r);output=x.get('output');passed=bool(x.get('passed'));status='model_fallback';details.update(x.get('details',{}))
  else:status='fallback_unavailable'
 except Exception as e:status='executor_error';details['error']=f'{type(e).__name__}: {e}'
 caps[r.task_type]=1.0 if passed else 0.0;out=Outcome(task.id,passed,1.0 if passed else 0.0,0.0,time.monotonic()-started,0,caps,details);return DispatchResult(r,out,output,status)
