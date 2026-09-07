from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,required=True)
 ap.add_argument("--duration-minutes",type=int,default=30)
 ap.add_argument("--workers",type=int,default=3)
 ap.add_argument("--interval-s",type=float,default=1.0)
 args=ap.parse_args()
 args.root.mkdir(parents=True,exist_ok=True)
 _SRC=Path(__file__).resolve().parents[1]
 env={**os.environ,"PYTHONPATH":str(_SRC),"PYTHONIOENCODING":"utf-8"}
 start=time.time();end=start+args.duration_minutes*60
 iters_per_worker=max(1,int((end-start)/max(args.interval_s,0.1)/args.workers))
 procs=[subprocess.Popen([sys.executable,"-m","evoagent.worker_soak","--root",str(args.root),"--worker",f"w{i}","--iters",str(iters_per_worker),"--interval",str(args.interval_s)],env=env) for i in range(args.workers)]
 start_ts=time.time()
 for proc in procs:proc.wait()
 eff_path=args.root/"effects.jsonl"
 eff=len(eff_path.read_text().splitlines()) if eff_path.exists() else 0
 report={"duration_minutes":args.duration_minutes,"workers":args.workers,"started_at_epoch":start,"finished_at_epoch":time.time(),"elapsed_s":time.time()-start,"unique_effects":eff,"per_worker_target":iters_per_worker}
 (args.root/"final-report.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2))
 return 0

if __name__=="__main__":sys.exit(main())
