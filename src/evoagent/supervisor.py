from __future__ import annotations
import time
from dataclasses import replace
from typing import Callable
from .durable_run import RunState,RunStore,TERMINAL_STATUSES
from .event_log import EventLog
from .lease import acquire
from .budget import budget_status

StepHandler=Callable[[RunState],RunState]

SKIPPED_STATUSES=TERMINAL_STATUSES | {"blocked"}

class WorkerSupervisor:
 def __init__(self,store:RunStore,events:EventLog,owner:str,lease_ttl_s:float=60.0):
  self.store=store;self.events=events;self.owner=owner;self.lease_ttl_s=lease_ttl_s
 def _expired(self,state:RunState,now:float)->bool:
  return bool(state.lease_owner) and state.lease_owner!=self.owner and state.lease_expires_at<=now
 def heartbeat(self,now:float|None=None)->list[RunState]:
  now=now or time.time();taken=[]
  for state in self.store.list():
   if state.status in SKIPPED_STATUSES:continue
   if not self._expired(state,now):continue
   renewed=acquire(state,self.owner,self.lease_ttl_s,now)
   self.store.save(renewed);self.events.append(state.run_id,"lease_takeover_after_timeout",{"previous_owner":state.lease_owner,"new_owner":self.owner,"lease_expires_at":renewed.lease_expires_at});taken.append(renewed)
  return taken
 def run_once(self,handler:StepHandler,now:float|None=None)->dict:
  self.heartbeat(now);now=now or time.time()
  for state in self.store.list():
   if state.status in SKIPPED_STATUSES:continue
   if state.lease_owner and state.lease_owner!=self.owner and state.lease_expires_at>now:continue
   if state.lease_owner==self.owner and state.lease_expires_at>now:state=replace(state,lease_owner="",lease_expires_at=0.0)
   if state.lease_owner:continue
   if state.next_wakeup_at>now:continue
   lease=acquire(state,self.owner,self.lease_ttl_s,now)
   gate=budget_status(lease,now)
   if not gate["allowed"]:
    killed=replace(lease,status="failed",lease_owner="",lease_expires_at=0.0,metadata={**lease.metadata,"kill_switch":gate})
    self.store.save(killed);self.events.append(lease.run_id,"kill_switch",gate);return {"worked":True,"status":"failed","run_id":lease.run_id}
   self.store.save(lease);self.events.append(state.run_id,"lease_acquired",{"owner":self.owner})
   try:
    updated=handler(replace(lease,attempt=lease.attempt+1))
    if updated.run_id!=lease.run_id:raise ValueError("handler changed run_id")
    if updated.status not in TERMINAL_STATUSES:updated=replace(updated,lease_owner="",lease_expires_at=0.0)
    self.store.save(updated);self.events.append(updated.run_id,"step_completed",{"status":updated.status,"attempt":updated.attempt});return {"worked":True,"status":updated.status,"run_id":updated.run_id}
   except Exception as exc:
    failed=replace(lease,status="blocked",lease_owner="",lease_expires_at=0.0,metadata={**lease.metadata,"last_error":f"{type(exc).__name__}: {exc}"})
    self.store.save(failed);self.events.append(lease.run_id,"step_failed",{"error":failed.metadata["last_error"]});return {"worked":True,"status":"blocked","run_id":lease.run_id}
  return {"worked":False,"reason":"no_eligible_run"}
