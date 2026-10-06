from __future__ import annotations
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path

KB=Path(os.environ.get('EVO_KB_DIR')or Path.home()/'.evoagent/kb')
PY=Path(os.environ.get('EVO_KB_PYTHON')or (KB/'.venv/Scripts/python.exe'if os.name=='nt'else KB/'.venv/bin/python'))

def search(query:str,n:int=10,year_min:int|None=None):
    cmd=[str(PY),'-X','utf8',str(KB/'kb_query_json.py'),query,'-n',str(n)]
    if year_min: cmd += ['--year-min',str(year_min)]
    run=subprocess.run(cmd,cwd=KB,capture_output=True,text=True,timeout=180,check=True)
    return json.loads(run.stdout)

def learn(root:Path,topic:str,n:int=10,year_min:int|None=None):
    rows=search(topic,n,year_min); rid=time.strftime('%Y%m%d-%H%M%S')
    record={'id':rid,'topic':topic,'query_sha256':hashlib.sha256(topic.encode()).hexdigest(),'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'papers':rows,'status':'evidence_collected'}
    out=root/'.evo/learning/runs'/f'{rid}.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return record,out

def main():
    p=argparse.ArgumentParser();p.add_argument('topic');p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('-n',type=int,default=10);p.add_argument('--year-min',type=int);a=p.parse_args();r,o=learn(a.root.resolve(),a.topic,a.n,a.year_min);print(json.dumps({'topic':r['topic'],'papers':len(r['papers']),'saved':str(o)},ensure_ascii=False))
if __name__=='__main__':main()
