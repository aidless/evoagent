from __future__ import annotations
import hashlib,json,os,time
from dataclasses import dataclass,field
from pathlib import Path
def _hf_hub_root():
 """Locate the HuggingFace cache in a platform-neutral way."""
 for var in ('HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE'):
  v=os.environ.get(var)
  if v:return Path(v)
 hf_home=os.environ.get('HF_HOME')
 if hf_home:return Path(hf_home)/'hub'
 if os.name=='nt':
  local=os.environ.get('LOCALAPPDATA')
  if local:return Path(local)/'huggingface'/'hub'
 return Path.home()/'.cache'/'huggingface'/'hub'
def _models_root():
 """Where local GGUF weights live. Override with EVO_MODELS_DIR."""
 v=os.environ.get('EVO_MODELS_DIR')
 if v:return Path(v)
 return Path.home()/'.evoagent'/'models'
def _snapshot_path(model_dir):
  p=Path(model_dir)/'snapshots'
  if not p.exists():return None
  children=sorted(c for c in p.iterdir() if c.is_dir())
  return children[0] if children else None
@dataclass(frozen=True)
class ModelSpec:
 backend:str;id:str;path:Path;family:str;size:str;quantization:str;context:int=4096;tool_call:bool=False;license:str='apache-2.0'
 def idstr(self):return self.id
@dataclass
class ModelBackendRegistry:
 path:Path;data:dict=field(default_factory=dict)
 def __post_init__(self):
  if self.path.exists():self.data=json.loads(self.path.read_text(encoding='utf-8-sig'))
  else:self.data={'backends':{}, 'history':[]}
 def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);t=self.path.with_suffix('.tmp');t.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,self.path)
 def _hash(self,p):
  if p.is_file():b=p.read_bytes()
  elif p.is_dir():import hashlib as h;b=b''
  else:return ''
  return hashlib.sha256(b).hexdigest() if len(b)<2**30 else hashlib.sha256(b[:2**20]).hexdigest()
 def register(self,spec:ModelSpec,level='experimental'):
  p=Path(spec.path)
  if not p.exists():raise FileNotFoundError(f'model path not found: {p}')
  sha=self._hash(p)
  self.data['backends'][spec.id]={'id':spec.id,'backend':spec.backend,'path':str(p),'family':spec.family,'size':spec.size,'quantization':spec.quantization,'context':spec.context,'tool_call':spec.tool_call,'license':spec.license,'sha256':sha,'level':level,'registered_at':time.strftime('%Y-%m-%dT%H:%M:%S')}
  self.data['history'].append({'action':'register','model':spec.id,'at':self.data['backends'][spec.id]['registered_at']});self._save()
 def list(self):return list(self.data['backends'].keys())
 def get(self,model_id):return self.data['backends'].get(model_id)
 def audit(self):return self.data
# (hf cache dir name / gguf file name, id, family, size, quantization, context, tool_call, license)
_HF_MODELS=[
 ('models--Qwen--Qwen2.5-1.5B-Instruct','qwen2.5-1.5b-instruct','qwen2.5','1.5B','safetensors',32768,True,'apache-2.0'),
 ('models--Qwen--Qwen2.5-3B-Instruct','qwen2.5-3b-instruct','qwen2.5','3B','safetensors',32768,True,'apache-2.0'),
 ('models--Qwen--Qwen2.5-7B-Instruct','qwen2.5-7b-instruct','qwen2.5','7B','safetensors',32768,True,'apache-2.0'),
 ('models--NousResearch--Hermes-3-Llama-3.2-3B','hermes-3-llama-3.2-3b','llama3.2','3B','safetensors',131072,True,'apache-2.0'),
]
_GGUF_MODELS=[
 ('mistral-7b-instruct-v0.2.Q4_K_M.gguf','mistral-7b-instruct-v0.2','mistral','7B','Q4_K_M',32768,True,'apache-2.0'),
 ('qwen2-7b-instruct-q4_k_m.gguf','qwen2-7b-instruct-gguf','qwen2','7B','Q4_K_M',32768,True,'apache-2.0'),
 ('llama-2-7b-chat.Q4_K_M.gguf','llama-2-7b-chat','llama2','7B','Q4_K_M',4096,False,'llama2-community'),
]
def default_specs():
 """Build the default candidate list from wherever weights actually live.

 The previous list hardcoded one developer's ``C:\\Users\\Administrator\\...`` HF cache
 and ``E:\\models\\...`` GGUF files. On any other machine -- CI included -- every
 ``register()`` raised FileNotFoundError, the skips were printed and swallowed,
 and the registry silently came up empty.
 """
 hub=_hf_hub_root();models=_models_root();specs=[]
 for repo_dir,mid,fam,size,quant,ctx,tool,lic in _HF_MODELS:
  snap=_snapshot_path(hub/repo_dir)
  specs.append(ModelSpec('hf_snapshot',mid,snap if snap else hub/repo_dir,fam,size,quant,ctx,tool,lic))
 for fname,mid,fam,size,quant,ctx,tool,lic in _GGUF_MODELS:
  specs.append(ModelSpec('gguf',mid,models/fname,fam,size,quant,ctx,tool,lic))
 return specs
def register_defaults(path:Path):
 r=ModelBackendRegistry(path)
 for m in default_specs():
  try:r.register(m)
  except Exception as e:print('skip',m.id,e)
 return r
