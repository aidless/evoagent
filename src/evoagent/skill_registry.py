from __future__ import annotations
import json,os,time
from dataclasses import asdict,dataclass
from pathlib import Path
LEVELS=('experimental','provisional','stable','production')
@dataclass(frozen=True)
class SkillSpec:
 name:str;version:str;task_type:str;entrypoint:str;input_schema:dict;output_schema:dict;permissions:tuple[str,...]=();risk:str='normal';level:str='experimental';evidence:dict=None
 @property
 def id(self):return f'{self.name}@{self.version}'
 def __post_init__(self):
  if not self.name or not self.version or not self.task_type or not self.entrypoint:raise ValueError('skill identity required')
  if self.level not in LEVELS:raise ValueError('invalid level')
  if self.risk not in ('normal','medium','high'):raise ValueError('invalid risk')
def _type_ok(v,t):return {'string':isinstance(v,str),'number':isinstance(v,(int,float)) and not isinstance(v,bool),'boolean':isinstance(v,bool),'object':isinstance(v,dict),'array':isinstance(v,list)}.get(t,False)
def validate_contract(data,schema):
 if not isinstance(data,dict):raise ValueError('contract value must be object')
 for k in schema.get('required',[]):
  if k not in data:raise ValueError('missing field: '+k)
 for k,v in data.items():
  if k in schema.get('properties',{}) and not _type_ok(v,schema['properties'][k]['type']):raise ValueError('wrong type: '+k)
 return True
class SkillRegistry:
 def __init__(self,path:Path,allowed_permissions=frozenset({'read_kb','local_compute','model_inference','code_sandbox'}),attestations=None,strict_attestation=False):
  self.path=path;self.allowed_permissions=allowed_permissions;self.attestations=attestations;self.strict_attestation=strict_attestation;self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'skills':{},'active':{},'history':[]}
 def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,self.path)
 def register(self,spec:SkillSpec):
  if spec.id in self.data['skills']:raise ValueError('immutable skill version already exists')
  denied=set(spec.permissions)-set(self.allowed_permissions)
  if denied:raise ValueError('permission denied: '+','.join(sorted(denied)))
  row=asdict(spec);row['evidence']=spec.evidence or {};row['registered_at']=time.strftime('%Y-%m-%dT%H:%M:%S');self.data['skills'][spec.id]=row;self.data['history'].append({'action':'register','skill_id':spec.id,'at':row['registered_at']});self._save();return row
 def activate(self,skill_id):
  row=self.data['skills'][skill_id]
  if self.strict_attestation and (not self.attestations or not self.attestations.verify(skill_id)['valid']):raise ValueError('skill attestation invalid')
  if row['level']=='experimental':raise ValueError('experimental skill cannot be active')
  old=self.data['active'].get(row['task_type']);self.data['active'][row['task_type']]=skill_id;self.data['history'].append({'action':'activate','skill_id':skill_id,'replaced':old,'at':time.strftime('%Y-%m-%dT%H:%M:%S')});self._save();return old
 def resolve(self,task_type):
  sid=self.data['active'].get(task_type)
  if sid and self.strict_attestation and (not self.attestations or not self.attestations.verify(sid)['valid']):return None
  return self.data['skills'].get(sid) if sid else None
