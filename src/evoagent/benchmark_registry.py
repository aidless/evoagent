from __future__ import annotations
import csv,os,re
from functools import lru_cache
from pathlib import Path
_REPO=Path(__file__).resolve().parents[2]
CSV=Path(os.environ.get('EVO_BENCHMARKS_CSV')or _REPO/'benchmarks/registry-v2/benchmarks.csv')
def norm(s):return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()
@lru_cache
def load():
 rows=[]
 with CSV.open(encoding='utf-8-sig',errors='replace') as f:
  for r in csv.DictReader(f):
   try:score=float(r['Score'])
   except:continue
   rows.append({**r,'score_value':score,'model_norm':norm(r['Model']),'benchmark_norm':norm(r['Benchmark']),'protocol_norm':norm(r['EvalProtocol'])})
 return rows
def query(model,benchmark,protocol=None):
 m,b,p=norm(model),norm(benchmark),norm(protocol or '');return [r for r in load() if r['model_norm']==m and r['benchmark_norm']==b and (not p or r['protocol_norm']==p)]
def validate_fact(model,benchmark,score,protocol=None,tolerance=.05):
 candidates=query(model,benchmark,protocol);matches=[r for r in candidates if abs(r['score_value']-float(score))<=tolerance];return {'valid':bool(matches),'matches':matches,'candidates':candidates,'protocol_required':len(query(model,benchmark))>1 and protocol is None}
def validate_quantitative_claim(text,tolerance=.05):
 low=norm(text);nums=[float(x) for x in re.findall(r'(?<![a-z])\d+(?:\.\d+)?(?=%|\s|$)',text)]
 candidates=[r for r in load() if r['model_norm'] in low and r['benchmark_norm'] in low]
 matches=[r for r in candidates if any(abs(r['score_value']-n)<=tolerance for n in nums)]
 return {'applicable':bool(candidates),'valid':bool(matches),'matches':matches,'candidates':candidates,'numbers':nums}
