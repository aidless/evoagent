from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from evoagent.durable_run import RunState,RunStore
from evoagent.event_log import EventLog
from evoagent.idempotency import IdempotencyRegistry

def _reserve(root:Path,key:str,effect_hash:str)->bool:
 idem=IdempotencyRegistry(root/"idempotency.json");row=idem.get(key)
 if row and row.get("status")=="completed":return False
 reservation=idem.reserve(key,effect_hash)
 return not reservation.get("duplicate",False)

def _complete(root:Path,key:str,result:dict)->None:
 IdempotencyRegistry(root/"idempotency.json").complete(key,result)

def _record_effect(root:Path,key:str)->None:
 f=root/"effects.jsonl"
 if f.exists() and key in f.read_text().splitlines():return
 with f.open("a") as handle:handle.write(key+"\n")

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,required=True)
 ap.add_argument("--worker",required=True)
 ap.add_argument("--iters",type=int,default=10)
 ap.add_argument("--interval",type=float,default=1.0)
 args=ap.parse_args()
 args.root.mkdir(parents=True,exist_ok=True)
 for i in range(args.iters):
  key=f"effect-{args.worker}-{i}"
  hash_=f"hash-{args.worker}-{i}"
  if _reserve(args.root,key,hash_):
   _record_effect(args.root,key)
   _complete(args.root,key,{"ok":True,"worker":args.worker,"i":i})
  time.sleep(args.interval)
 return 0

if __name__=="__main__":sys.exit(main())
