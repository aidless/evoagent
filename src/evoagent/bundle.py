import os,hashlib,json,time
from pathlib import Path
from .attestation import hash_file
from .multisig import verify_multisig
class BundleRegistry:
 def __init__(self,path):self.path=path;self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'bundles':{}, 'history':[]}
 def _save(self):self.path.parent.mkdir(parents=True,exist_ok=True);t=self.path.with_suffix('.tmp');t.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,self.path)
 @staticmethod
 def _digest(manifest):return hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 def create(self,name,source_files,config_files,skill_registry,attestations,metadata=None,required_signers=None):
  active=skill_registry.data.get('active',{});skills={}
  for task,sid in sorted(active.items()):
   a=attestations.data.get('attestations',{}).get(sid)
   if not a:raise ValueError('active skill missing attestation: '+sid)
   if not attestations.verify(sid)['valid']:raise ValueError('active skill attestation invalid: '+sid)
   spec=skill_registry.data['skills'][sid];spec_hash=hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest();skills[task]={'skill_id':sid,'spec_hash':spec_hash,'source_hash':a['source_hash'],'tests_hash':a['tests_hash'],'datasets_hash':a['datasets_hash'],'lock_hash':a['lock_hash']}
  files={'sources':{str(Path(p).resolve()):hash_file(Path(p)) for p in source_files},'configs':{str(Path(p).resolve()):hash_file(Path(p)) for p in config_files}}
  manifest={'name':name,'active_skills':skills,'files':files,'required_signers':sorted(required_signers) if required_signers else [],'metadata':metadata or {}};digest=self._digest(manifest);bid=f'{name}@{digest[:12]}';row={'bundle_id':bid,'sha256':digest,'manifest':manifest,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S')};self.data['bundles'][bid]=row;self.data['history'].append({'action':'create','bundle_id':bid,'at':row['created_at']});self._save();return row
 def verify(self,bundle_id,skill_registry,attestations):
  row=self.data['bundles'].get(bundle_id)
  if not row:return {'valid':False,'reason':'missing_bundle'}
  changed=[];m=row['manifest']
  for group,items in m['files'].items():
   for path,expected in items.items():
    p=Path(path);actual=hash_file(p) if p.exists() else None
    if actual!=expected:changed.append({'group':group,'path':path,'expected':expected,'actual':actual})
  for skill in m['active_skills'].values():
   sid=skill['skill_id'];v=attestations.verify(sid)
   if not v['valid']:changed.append({'group':'attestation','skill_id':sid,'reason':v['reason']})
  return {'valid':not changed,'reason':'ok' if not changed else 'bundle_changed','changed':changed}
 def list(self):return list(self.data['bundles'].keys())
class BundleVerifier:
 def __init__(self,bundle_registry,attestations,signature_registry=None,trusted_keys=None,required_signers=None):
  self.bundle=bundle_registry;self.attestations=attestations;self.signatures=signature_registry;self.trusted_keys=trusted_keys or {};self.required_signers=required_signers or []
 def __call__(self,bundle_id):
  if not bundle_id:return {'valid':False,'reason':'missing_bundle_id'}
  row=self.bundle.data['bundles'].get(bundle_id)
  if not row:return {'valid':False,'reason':'bundle_not_found'}
  v=self.bundle.verify(bundle_id,self.bundle,self.attestations)
  if not v['valid']:return v
  m=row['manifest'];required=m.get('required_signers',[]) or self.required_signers
  if required and self.signatures is None:return {'valid':False,'reason':'signature_registry_missing','required_signers':required}
  if required:
   envs=[]
   if self.signatures is not None:
    rec=self.signatures.data.get('signatures',{}).get(bundle_id)
    if rec and 'envelope' in rec:envs=[rec['envelope']]
    elif rec and 'signers' in rec:envs=rec['signers']
   qr=verify_multisig(envs,row,self.trusted_keys,required)
   if not qr['valid']:return {'valid':False,'reason':'quorum_not_met','detail':qr.get('reason'),'required_signers':required,'valid_count':qr.get('valid_count',0)}
  if self.signatures is not None:
   s=self.signatures.verify(row)
   if not s['valid']:return {'valid':False,'reason':'signature_invalid','detail':s.get('reason')}
  return {'valid':True,'reason':'ok','bundle_id':bundle_id,'required_signers':required}
