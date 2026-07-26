from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
from .idempotency import IdempotencyRegistry
from .core import save_json

PHASES=('reserve','checkpoint','effect')

def worker(root:Path,kill_after:str=''):
 idem=IdempotencyRegistry(root/'idempotency.json');key='effect-1';reservation=idem.reserve(key,'effect-hash')
 if reservation.get('duplicate') and reservation.get('status')=='completed':return 0
 if kill_after=='reserve':os._exit(17)
 save_json(root/'checkpoint.json',{'phase':'checkpoint','key':key})
 if kill_after=='checkpoint':os._exit(17)
 effects=root/'effects.jsonl';existing=[x for x in effects.read_text().splitlines() if x.strip()] if effects.exists() else []
 if key not in existing:
  with effects.open('a') as f:f.write(key+'\n')
 if kill_after=='effect':os._exit(17)
 idem.complete(key,{'ok':True});return 0

def recover(root:Path):
 idem=IdempotencyRegistry(root/'idempotency.json');row=idem.get('effect-1');effects=root/'effects.jsonl';performed=effects.exists() and 'effect-1' in effects.read_text().splitlines()
 if row and row.get('status')=='reserved':idem.resolve('effect-1',performed,{'ok':True} if performed else None)
 return worker(root)

def run(root:Path,n:int=100):
 rows=[]
 for i in range(n):
  with tempfile.TemporaryDirectory(prefix='evo-os-recovery-') as td:
   p=Path(td);phase=PHASES[i%len(PHASES)];proc=subprocess.run([sys.executable,'-m','evoagent.os_recovery','--worker','--root',str(p),'--kill-after',phase],env={**os.environ,'PYTHONPATH':str(root/'src')},capture_output=True)
   recovery=recover(p);effects=(p/'effects.jsonl').read_text().splitlines() if (p/'effects.jsonl').exists() else [];idem=IdempotencyRegistry(p/'idempotency.json').get('effect-1');passed=proc.returncode==17 and recovery==0 and effects==['effect-1'] and idem and idem['status']=='completed';rows.append({'case':i+1,'kill_after':phase,'worker_exit':proc.returncode,'recovery_exit':recovery,'effects':len(effects),'passed':passed})
 result={'cases':n,'passed':sum(r['passed'] for r in rows),'failed':sum(not r['passed'] for r in rows),'duplicate_effects':sum(max(0,r['effects']-1) for r in rows),'rows':rows};save_json(root/'.evo/os-recovery-report.json',result);return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--root',type=Path,required=True);ap.add_argument('--kill-after',default='');ap.add_argument('--cases',type=int,default=100);a=ap.parse_args();print(json.dumps(worker(a.root,a.kill_after) if a.worker else run(a.root,a.cases),indent=2));
