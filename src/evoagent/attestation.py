from __future__ import annotations
import hashlib,importlib,inspect,json,os,time
from dataclasses import dataclass,asdict
from pathlib import Path
def hash_file(path:Path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def hash_paths(paths):
 rows=[]
 for raw in sorted(map(Path,paths),key=lambda x:str(x).lower()):
  if raw.is_dir():files=sorted((x for x in raw.rglob('*') if x.is_file()),key=lambda x:str(x).lower())
  else:files=[raw]
  for p in files:
   if not p.exists():raise FileNotFoundError(p)
   rows.append({'path':str(p.resolve()),'sha256':hash_file(p)})
 return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest(),rows
def entrypoint_path(entrypoint,allowed_prefixes=('evoagent.',)):
 mod,sep,_=entrypoint.partition(':')
 if not sep or not any(mod.startswith(x) for x in allowed_prefixes):raise ValueError('entrypoint not allowed')
 m=importlib.import_module(mod);p=inspect.getsourcefile(m)
 if not p:raise ValueError('entrypoint has no source file')
 return Path(p)
@dataclass(frozen=True)
class Attestation:
 skill_id:str;entrypoint:str;source_hash:str;tests_hash:str;datasets_hash:str;lock_hash:str;files:dict;created_at:str
class AttestationRegistry:
 def __init__(self,path:Path):self.path=path;self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'attestations':{},'history':[]}
 def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);t=self.path.with_suffix('.tmp');t.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,self.path)
 def attest(self,skill_id,entrypoint,tests=(),datasets=(),locks=()):
  source=entrypoint_path(entrypoint);sh,sfiles=hash_paths([source]);th,tfiles=hash_paths(tests) if tests else ('',[]);dh,dfiles=hash_paths(datasets) if datasets else ('',[]);lh,lfiles=hash_paths(locks) if locks else ('',[]);a=Attestation(skill_id,entrypoint,sh,th,dh,lh,{'source':sfiles,'tests':tfiles,'datasets':dfiles,'locks':lfiles},time.strftime('%Y-%m-%dT%H:%M:%S'));self.data['attestations'][skill_id]=asdict(a);self.data['history'].append({'action':'attest','skill_id':skill_id,'at':a.created_at});self._save();return a
 def verify(self,skill_id):
  a=self.data['attestations'].get(skill_id)
  if not a:return {'valid':False,'reason':'missing_attestation'}
  changed=[]
  for group,rows in a['files'].items():
   for x in rows:
    p=Path(x['path']);actual=hash_file(p) if p.exists() else None
    if actual!=x['sha256']:changed.append({'group':group,'path':x['path'],'expected':x['sha256'],'actual':actual})
  return {'valid':not changed,'reason':'ok' if not changed else 'artifact_changed','changed':changed}
