import csv,json
from pathlib import Path
from collections import defaultdict
class BenchmarkAggregator:
 def __init__(self,csv_path:Path):
  self.csv_path=csv_path;self.rows=[];self.by_model=defaultdict(list);self.by_benchmark=defaultdict(list)
  if csv_path.exists():
   with open(csv_path,encoding='utf-8-sig',errors='replace') as f:
    r=csv.DictReader(f)
    for row in r:
     self.rows.append(row)
     self.by_model[row['Model']].append(row)
     self.by_benchmark[row['Benchmark']].append(row)
 def summary(self):
  return {'rows':len(self.rows),'unique_models':len(self.by_model),'unique_benchmarks':len(self.by_benchmark),'benchmarks':sorted(self.by_benchmark),'models':sorted(self.by_model)}
 def by_family(self):
  f=defaultdict(int)
  for m in self.by_model:
   for k in m.split():
    if k.isalpha():f[k]+=1
  return dict(f)
if __name__=='__main__':
  p=Path(os.environ.get('EVO_BENCHMARKS_CSV')or Path(__file__).resolve().parents[2]/'benchmarks/registry-v2/benchmarks.csv')
  a=BenchmarkAggregator(p)
  print(json.dumps(a.summary(),indent=2,ensure_ascii=False))
  print('family counts',a.by_family())
