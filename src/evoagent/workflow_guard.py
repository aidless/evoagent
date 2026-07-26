from __future__ import annotations
from dataclasses import asdict
from typing import Callable
from .action_policy import ActionRequest
from .guarded_executor import GuardedExecutor
from .tool_manifest import DEFAULT_TOOL_MANIFESTS,ToolManifest
from .workflow import Step,StepResult

class GuardedHandlerMap(dict):
 guarded=True

def make_guarded_handlers(handlers:dict[str,Callable],guard:GuardedExecutor,run_id:str,approval_resolver:Callable[[Step],bool]|None=None,manifests:dict[str,ToolManifest]|None=None):
 manifests=manifests or DEFAULT_TOOL_MANIFESTS;wrapped=GuardedHandlerMap()
 for name,handler in handlers.items():
  def build(action,fn):
   def guarded(step,ctx):
    manifest=manifests.get(action)
    if manifest is None:return StepResult(step.id,False,status='policy_manifest_missing')
    request=ActionRequest(step.id,manifest.policy_tool,{'action':action,'input':step.input},manifest.filesystem_scope,manifest.network_scope,manifest.estimated_cost,manifest.reversible)
    key=f'{run_id}:{step.id}:{request.arguments_sha256}'
    approved=bool(approval_resolver and approval_resolver(step))
    result=guard.execute(run_id,request,key,lambda:asdict(fn(step,ctx)),approved=approved)
    if result['status'] in ('completed','reused'):return StepResult(**result['result'])
    return StepResult(step.id,False,status=result['status'],details={'policy_decision':result.get('decision',{})})
   return guarded
  wrapped[name]=build(name,handler)
 return wrapped
