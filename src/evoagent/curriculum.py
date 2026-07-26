from __future__ import annotations
import argparse,json,time
from pathlib import Path
from .knowledge import learn

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--limit',type=int,default=0);p.add_argument('-n',type=int,default=8);a=p.parse_args();root=a.root.resolve();cfg=json.loads((root/'curriculum.json').read_text(encoding='utf-8-sig'));topics=cfg['topics'][:a.limit or None];results=[]
 for t in topics:
  try:r,out=learn(root,t['query'],a.n,t.get('year_min'));results.append({'id':t['id'],'status':'ok','papers':len(r['papers']),'run':str(out)})
  except Exception as e:results.append({'id':t['id'],'status':'failed','reason':f'{type(e).__name__}: {e}'})
 manifest={'started_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'topics':results};out=root/'.evo/learning/curriculum-last.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
