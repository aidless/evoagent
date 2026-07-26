from __future__ import annotations
import json,os
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class LoraBackendSpec:
 id:str;family:str;quantization:str;requires_gpu:bool=True;min_vram_gb:float=8.0;config_module:str='peft';algorithm:str='qlora'
 def runtime_check(self)->dict:
  missing=[]
  try:import peft
  except Exception:missing.append('peft')
  try:import bitsandbytes
  except Exception:missing.append('bitsandbytes')
  try:import accelerate
  except Exception:missing.append('accelerate')
  try:import torch
  except Exception:missing.append('torch')
  gpu=False;vram_gb=0.0
  try:
   import torch
   if torch.cuda.is_available():gpu=True;vram_gb=torch.cuda.get_device_properties(0).total_memory/(1024**3) if torch.cuda.device_count()>0 else 0
  except Exception:pass
  return {'id':self.id,'available':not missing and (not self.requires_gpu or gpu) and vram_gb>=self.min_vram_gb,'missing_modules':missing,'gpu':gpu,'vram_gb':round(vram_gb,2),'min_vram_gb':self.min_vram_gb}
class LoraBackendRegistry:
 def __init__(self,path:Path):self.path=path;self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'backends':{}, 'history':[]}
 def register(self,spec:LoraBackendSpec,level='experimental'):
  if spec.id in self.data['backends']:raise ValueError('backend id already exists')
  rc=spec.runtime_check();self.data['backends'][spec.id]={'id':spec.id,'family':spec.family,'quantization':spec.quantization,'requires_gpu':spec.requires_gpu,'min_vram_gb':spec.min_vram_gb,'algorithm':spec.algorithm,'level':level,'runtime':rc,'created_at':__import__('time').strftime('%Y-%m-%dT%H:%M:%S')};self._save();return rc
 def audit(self):return self.data
 def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);t=self.path.with_suffix('.tmp');t.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,self.path)
def build_default_backends(path:Path):
  reg=LoraBackendRegistry(path)
  reg.register(LoraBackendSpec(id='peft-qlora-4bit-qwen',family='qwen2-7b',quantization='qlora-4bit',requires_gpu=True,min_vram_gb=8.0,algorithm='qlora',config_module='peft'),level='experimental')
  return reg
