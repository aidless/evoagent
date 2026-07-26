from __future__ import annotations
import hashlib,json,os,time
from dataclasses import asdict,dataclass,field
from pathlib import Path
from .attestation import hash_file
@dataclass
class LoraSpec:
 base_model:str;adapter_name:str;rank:int=16;alpha:int=32;target_modules:tuple[str,...]=('q_proj','k_proj','v_proj');quantization:str='qlora-4bit';target_task:str='general';version:str='1'
 def __post_init__(self):
  if self.rank<=0 or self.alpha<=0:raise ValueError('rank and alpha must be positive')
  if not self.base_model:raise ValueError('base_model required')
 def id(self):return f'{self.adapter_name}@{self.version}'
 def to_dict(self):return asdict(self)
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True)
@dataclass
class AdapterArtifacts:
 config:dict;weights_path:Path;data_manifest_hash:str;trained_tokens:int=0;trained_steps:int=0
 def attest(self,spec:LoraSpec,base_model_path:Path,data_manifest_path:Path):
  h=hashlib.sha256(self.config.__repr__().encode()).hexdigest()
  for p in (self.weights_path,base_model_path,data_manifest_path):
   if not Path(p).exists():raise FileNotFoundError(p)
  return {'lora_id':spec.id(),'lora_json_sha256':h,'weights_sha256':hash_file(self.weights_path),'base_model_sha256':hash_file(base_model_path),'data_manifest_sha256':hash_file(data_manifest_path),'trained_tokens':self.trained_tokens,'trained_steps':self.trained_steps,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S')}
def build_adapter(spec:LoraSpec,data_manifest_path:Path,base_model_path:Path,out_dir:Path,train_steps:int=0,train_tokens:int=0)->dict:
 out_dir.mkdir(parents=True,exist_ok=True)
 weights_path=out_dir/f'{spec.adapter_name}_v{spec.version}.safetensors.json'
 weights_path.write_text(json.dumps({'format':'placeholder','rank':spec.rank,'alpha':spec.alpha,'target_modules':list(spec.target_modules),'base_model':spec.base_model}))
 cfg=spec.to_dict();cfg_path=out_dir/f'{spec.adapter_name}_v{spec.version}.json';cfg_path.write_text(json.dumps(cfg,indent=2))
 artifacts=AdapterArtifacts(config=cfg,weights_path=weights_path,data_manifest_hash=hash_file(data_manifest_path),trained_tokens=train_tokens,trained_steps=train_steps)
 attestation=artifacts.attest(spec,base_model_path,data_manifest_path)
 out=Path(out_dir)/f'{spec.adapter_name}_v{spec.version}.attestation.json';out.write_text(json.dumps(attestation,indent=2))
 return attestation
def verify_adapter(attestation_path:Path,spec:LoraSpec,base_model_path:Path,data_manifest_path:Path)->dict:
  a=json.loads(Path(attestation_path).read_text(encoding='utf-8-sig'))
  ok=True;reasons=[]
  for key,path in [('weights_sha256',spec if False else Path(attestation_path).with_name(Path(attestation_path).stem.replace('.attestation','')+'.safetensors.json')),('base_model_sha256',base_model_path),('data_manifest_sha256',data_manifest_path)]:
   if not Path(path).exists():ok=False;reasons.append(f'missing:{key}');continue
   if hash_file(Path(path))!=a[key]:ok=False;reasons.append(f'mismatch:{key}')
  return {'valid':ok,'reasons':reasons,'attestation':a}
