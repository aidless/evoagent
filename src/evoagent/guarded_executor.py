from __future__ import annotations
from typing import Any,Callable
from .action_policy import ActionPolicy,ActionRequest,PolicyEffect
from .event_log import EventLog
from .idempotency import IdempotencyRegistry

class GuardedExecutor:
 def __init__(self,policy:ActionPolicy,idempotency:IdempotencyRegistry,events:EventLog):self.policy=policy;self.idempotency=idempotency;self.events=events
 def execute(self,run_id:str,request:ActionRequest,idempotency_key:str,executor:Callable[[],Any],approved:bool=False)->dict:
  decision=self.policy.evaluate(request);self.events.append(run_id,'policy_decision',decision.as_dict())
  if decision.effect is PolicyEffect.DENY:return {'status':'denied','decision':decision.as_dict(),'executed':False}
  if decision.effect is PolicyEffect.APPROVE and not approved:return {'status':'approval_required','decision':decision.as_dict(),'executed':False}
  reservation=self.idempotency.reserve(idempotency_key,request.arguments_sha256)
  if reservation.get('duplicate'):
   if reservation['status']=='completed':return {'status':'reused','executed':False,'result':reservation['result'],'decision':decision.as_dict()}
   return {'status':'uncertain_prior_attempt','executed':False,'decision':decision.as_dict()}
  self.events.append(run_id,'action_started',{'action_id':request.action_id,'idempotency_key':idempotency_key})
  try:
   result=executor();self.idempotency.complete(idempotency_key,result);self.events.append(run_id,'action_completed',{'action_id':request.action_id,'idempotency_key':idempotency_key});return {'status':'completed','executed':True,'result':result,'decision':decision.as_dict()}
  except Exception as exc:
   self.events.append(run_id,'action_uncertain',{'action_id':request.action_id,'idempotency_key':idempotency_key,'error':f'{type(exc).__name__}: {exc}'});return {'status':'uncertain_prior_attempt','executed':True,'error':f'{type(exc).__name__}: {exc}','decision':decision.as_dict()}
