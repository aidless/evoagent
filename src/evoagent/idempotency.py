from __future__ import annotations
from pathlib import Path
from typing import Any
from .core import load_json,save_json

class IdempotencyRegistry:
 def __init__(self,path:Path): self.path=path; self.data=load_json(path) if path.exists() else {"records":{}}
 def reserve(self,key:str,action_sha256:str)->dict:
  if not key: raise ValueError("idempotency key required")
  row=self.data["records"].get(key)
  if row:
   if row["action_sha256"]!=action_sha256: raise RuntimeError("idempotency_conflict")
   return {**row,"duplicate":True}
  row={"key":key,"action_sha256":action_sha256,"status":"reserved","result":None};self.data["records"][key]=row;save_json(self.path,self.data);return {**row,"duplicate":False}
 def complete(self,key:str,result:Any)->dict:
  row=self.data["records"][key];row["status"]="completed";row["result"]=result;save_json(self.path,self.data);return row
 def resolve(self,key:str,performed:bool,result:Any=None)->dict:
  row=self.data["records"][key]
  if row["status"]=="completed":return row
  if performed:return self.complete(key,result)
  del self.data["records"][key];save_json(self.path,self.data);return {"key":key,"status":"cleared"}
 def get(self,key:str): return self.data["records"].get(key)
