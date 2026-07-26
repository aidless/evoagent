from __future__ import annotations
import hashlib,json,time,uuid
from pathlib import Path
from typing import Any
from .core import load_json,save_json

class CheckpointStore:
 def __init__(self,root:Path):self.root=root;root.mkdir(parents=True,exist_ok=True)
 def create(self,run_id:str,state:dict[str,Any])->dict:
  cid=f"cp-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}";payload={"checkpoint_id":cid,"run_id":run_id,"created_at":time.strftime('%Y-%m-%dT%H:%M:%S'),"state":state};payload["state_sha256"]=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest();save_json(self.root/f"{cid}.json",payload);return payload
 def load(self,checkpoint_id:str)->dict:
  row=load_json(self.root/f"{checkpoint_id}.json");actual=hashlib.sha256(json.dumps(row["state"],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  if actual!=row["state_sha256"]:raise RuntimeError("checkpoint_changed")
  return row
