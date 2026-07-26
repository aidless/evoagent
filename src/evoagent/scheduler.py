from __future__ import annotations
import time
from dataclasses import replace
from typing import Callable
from .budget import budget_status
from .durable_run import RunState,RunStore,TERMINAL_STATUSES
from .event_log import EventLog
from .lease import acquire,release

StepHandler=Callable[[RunState],RunState]

class DurableScheduler:
 def __init__(self,store:RunStore,events:EventLog,owner:str,lease_ttl_s:float=60):self.store=store;self.events=events;self.owner=owner;self.lease_ttl_s=lease_ttl_s
 def eligible(self,now:float|None=None):
  now=now or time.time();return [r for r in self.store.list() if r.status not in TERMINAL_STATUSES and r.next_wakeup_at<=now and (not r.lease_owner or r.lease_expires_at<=now or r.lease_owner==self.owner)]
 def run_once(self,handler:StepHandler,now:float|None=None)->dict:
  rows=self.eligible(now)
  if not rows:return {"worked":False,"reason":"no_eligible_run"}
  state=acquire(rows[0],self.owner,self.lease_ttl_s,now);self.store.save(state);self.events.append(state.run_id,"lease_acquired",{"owner":self.owner,"attempt":state.attempt})
  gate=budget_status(state,now)
  if not gate["allowed"]:
   state=replace(state,status="failed",metadata={**state.metadata,"kill_switch":gate});self.store.save(state);self.events.append(state.run_id,"kill_switch",gate);return {"worked":True,"status":"failed","run_id":state.run_id}
  try:
   updated=handler(replace(state,attempt=state.attempt+1));
   if updated.run_id!=state.run_id:raise ValueError("handler changed run_id")
   if updated.status not in TERMINAL_STATUSES:updated=release(updated,self.owner)
   self.store.save(updated);self.events.append(updated.run_id,"step_completed",{"status":updated.status,"attempt":updated.attempt});return {"worked":True,"status":updated.status,"run_id":updated.run_id}
  except Exception as exc:
   failed=replace(state,status="blocked",lease_owner="",lease_expires_at=0.0,metadata={**state.metadata,"last_error":f"{type(exc).__name__}: {exc}"});self.store.save(failed);self.events.append(state.run_id,"step_failed",{"error":failed.metadata["last_error"]});return {"worked":True,"status":"blocked","run_id":state.run_id}
