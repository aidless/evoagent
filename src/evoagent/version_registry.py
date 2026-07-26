from __future__ import annotations
import json,os,time
from pathlib import Path
LEVELS=('experimental','provisional','stable','production')
REQUIRED={
 ('experimental','provisional'):('development_passed','rollback_available'),
 ('provisional','stable'):('statistical_passed','hidden_passed','safety_passed','rollback_available','bundle_signature_valid'),
 ('stable','production'):('shadow_passed','human_approved','safety_passed','rollback_available','bundle_signature_valid')}
class VersionRegistry:
 def __init__(self,path:Path):self.path=path;self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'versions':{},'history':[]}
 def _save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,self.path)
 def register(self,version_id,component,level='experimental',evidence=None):
  if level not in LEVELS:raise ValueError('invalid level')
  if version_id in self.data['versions']:raise ValueError('version already exists')
  row={'version_id':version_id,'component':component,'level':level,'evidence':evidence or {},'created_at':time.strftime('%Y-%m-%dT%H:%M:%S')};self.data['versions'][version_id]=row;self.data['history'].append({'action':'register',**row});self._save();return row
 def transition(self,version_id,target,evidence=None,reason=''):
  if target not in LEVELS:raise ValueError('invalid level')
  row=self.data['versions'][version_id];current=row['level'];ci,ti=LEVELS.index(current),LEVELS.index(target);ev=evidence or {}
  if ti>ci:
   if ti!=ci+1:raise ValueError('level skipping is forbidden')
   missing=[k for k in REQUIRED[(current,target)] if not ev.get(k)]
   if missing:raise ValueError('missing evidence: '+','.join(missing))
  row['level']=target;row['evidence']={**row.get('evidence',{}),**ev};event={'action':'transition','version_id':version_id,'from':current,'to':target,'evidence':ev,'reason':reason,'at':time.strftime('%Y-%m-%dT%H:%M:%S')};self.data['history'].append(event);self._save();return event
 def annotate(self,version_id,evidence,reason=''):
  if version_id not in self.data['versions']:raise KeyError(version_id)
  if not isinstance(evidence,dict) or not evidence:raise ValueError('evidence annotation required')
  row=self.data['versions'][version_id];row['evidence']={**row.get('evidence',{}),**evidence};event={'action':'annotate','version_id':version_id,'evidence':evidence,'reason':reason,'at':time.strftime('%Y-%m-%dT%H:%M:%S')};self.data['history'].append(event);self._save();return event
 def get(self,version_id):return self.data['versions'][version_id]
