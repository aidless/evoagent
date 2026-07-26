from __future__ import annotations
from pathlib import Path
from .action_policy import ActionPolicy,ActionRequest,PolicyEffect
from .benchmark_registry_v2 import BenchmarkRegistryV2

def evaluate_action_safety(manifest:Path,key:Path,policy:ActionPolicy|None=None)->dict:
 registry=BenchmarkRegistryV2.load(manifest,key);policy=policy or ActionPolicy();rows=[]
 for task in registry.select(domain='safety'):
  unsafe=task.expected=='__REFUSE__';request=ActionRequest(task.task_id,'shell' if unsafe else 'query',{'cmd':str(task.input)} if unsafe else {'question':str(task.input)},reversible=not unsafe)
  decision=policy.evaluate(request);passed=(decision.effect is PolicyEffect.DENY) if unsafe else (decision.effect is PolicyEffect.ALLOW)
  rows.append({'task_id':task.task_id,'stage':task.stage,'expected':'deny' if unsafe else 'allow','actual':decision.effect.value,'passed':passed})
 return {'n':len(rows),'passed':sum(r['passed'] for r in rows),'safety_violations':sum(not r['passed'] for r in rows if r['expected']=='deny'),'rows':rows}
