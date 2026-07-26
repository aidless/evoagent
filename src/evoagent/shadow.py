from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
from .promotion_gate import evaluate_promotion
from .protocol import Outcome,Run
from .version_registry import VersionRegistry

def redact(text:str)->str:
 text=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','<EMAIL>',text)
 text=re.sub(r'(?<!\d)(?:\+?\d[\d -]{8,}\d)(?!\d)','<PHONE>',text)
 text=re.sub(r'(?i)(api[_ -]?key|token|password)\s*[:=]\s*[^\s,;]+',r'\1=<SECRET>',text)
 return text
def digest(value:str)->str:return hashlib.sha256(value.encode()).hexdigest()
class ShadowRecorder:
 def __init__(self,path:Path,baseline_id:str,candidate_id:str):self.path=path;self.baseline_id=baseline_id;self.candidate_id=candidate_id;path.parent.mkdir(parents=True,exist_ok=True)
 def record(self,task_id,input_text,baseline:Outcome,candidate:Outcome,store_redacted=True):
  if baseline.task_id!=task_id or candidate.task_id!=task_id:raise ValueError('task id mismatch')
  row={'task_id':task_id,'input_sha256':digest(input_text),'input_redacted':redact(input_text) if store_redacted else None,'baseline_id':self.baseline_id,'candidate_id':self.candidate_id,'baseline':baseline.__dict__,'candidate':candidate.__dict__,'at':time.strftime('%Y-%m-%dT%H:%M:%S')}
  with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  return row
 def rows(self):return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip()] if self.path.exists() else []
 def summarize(self,gate=None):
  rows=self.rows();bo=tuple(Outcome(**x['baseline']) for x in rows);co=tuple(Outcome(**x['candidate']) for x in rows);h=digest('\n'.join(sorted(x.task_id for x in bo)));decision=evaluate_promotion(Run('shadow-b',self.baseline_id,h,bo),Run('shadow-c',self.candidate_id,h,co),**(gate or {})) if rows else {'promote':False,'reasons':['no_shadow_data']};return {'n':len(rows),'baseline_id':self.baseline_id,'candidate_id':self.candidate_id,'decision':decision,'shadow_passed':bool(decision.get('promote'))}
def enforce_shadow_safety(summary,registry:VersionRegistry,candidate_id:str):
 d=summary['decision'];unsafe=d.get('safety_violations',0)>0
 if unsafe:
  current=registry.get(candidate_id)['level']
  if current!='experimental':return registry.transition(candidate_id,'experimental',{'shadow_summary':summary},reason='automatic shadow safety downgrade')
 return None
def production_evidence(summary,human_approved:bool):
 return {'shadow_passed':bool(summary.get('shadow_passed')),'human_approved':bool(human_approved),'safety_passed':summary.get('decision',{}).get('safety_violations',0)==0,'rollback_available':True,'shadow_n':summary.get('n',0)}
