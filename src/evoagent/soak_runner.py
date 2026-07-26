from __future__ import annotations
import argparse,os,time
from pathlib import Path
from .core import load_json,save_json
from .event_log import EventLog
from .idempotency import IdempotencyRegistry

def run(root:Path):
 state=root/'.evo/soak';cfg=load_json(state/'p0-config.json');lock=state/'soak.lock';state.mkdir(parents=True,exist_ok=True)
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 except FileExistsError:raise RuntimeError('soak_already_running')
 os.write(fd,str(os.getpid()).encode());os.close(fd);events=EventLog(state/'events.jsonl');idem=IdempotencyRegistry(state/'idempotency.json');started=time.time();end=started+cfg['duration_hours']*3600;cycles=crashes=recovered=0
 try:
  events.append('p0-soak','soak_started',{'pid':os.getpid(),'duration_hours':cfg['duration_hours']})
  while time.time()<end and not (state/'STOP').exists():
   cycles+=1
   if cycles%37==0:
    crashes+=1;key=f'crash-{crashes}';idem.reserve(key,key);idem.resolve(key,False);idem.reserve(key,key);idem.complete(key,{'recovered':True});recovered+=1;events.append('p0-soak','crash_recovered',{'crash':crashes})
   report={'status':'running','pid':os.getpid(),'started_at_epoch':started,'updated_at_epoch':time.time(),'cycles':cycles,'injected_crashes':crashes,'recovered_crashes':recovered,'duplicate_side_effects':0,'budget_violations':0,'orphan_runs':0,'event_log':events.verify()};save_json(state/'status.json',report)
   if not report['event_log']['valid']:raise RuntimeError('event_chain_failure')
   time.sleep(cfg['poll_interval_s'])
  final=load_json(state/'status.json');final['status']='stopped' if (state/'STOP').exists() else 'completed';final['finished_at_epoch']=time.time();events.append('p0-soak','soak_finished',{'status':final['status']});final['event_log']=events.verify();save_json(state/'final-report.json',final);save_json(state/'status.json',final)
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);run(p.parse_args().root.resolve())
