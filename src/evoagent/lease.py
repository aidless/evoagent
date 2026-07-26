from __future__ import annotations
import time
from dataclasses import replace
from .durable_run import RunState


def acquire(state: RunState, owner: str, ttl_s: float, now: float | None = None) -> RunState:
    now=now or time.time()
    if not owner or ttl_s<=0: raise ValueError("owner and positive ttl required")
    if state.lease_owner and state.lease_owner!=owner and state.lease_expires_at>now: raise RuntimeError("lease_held")
    return replace(state,lease_owner=owner,lease_expires_at=now+ttl_s,last_heartbeat=now,status="running")

def heartbeat(state: RunState, owner: str, ttl_s: float, now: float | None = None) -> RunState:
    now=now or time.time()
    if state.lease_owner!=owner or state.lease_expires_at<=now: raise RuntimeError("lease_lost")
    return replace(state,lease_expires_at=now+ttl_s,last_heartbeat=now)

def release(state: RunState, owner: str) -> RunState:
    if state.lease_owner!=owner: raise RuntimeError("lease_not_owned")
    return replace(state,lease_owner="",lease_expires_at=0.0)
