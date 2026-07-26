from __future__ import annotations
import argparse,json,time
from pathlib import Path
from .date_generator import generate as gen_date
from .logic_generator import generate as gen_logic
from .reasoning_tools import solve_date,solve_logic

def eval_cases(cases,solver):
 rows=[]
 for x in cases:
  p=solver(x['input']);ok=p is not None and f'({p})'==x['target'];rows.append({'id':x['id'],'prediction':p,'target':x['target'],'passed':ok,'input':x['input'] if not ok else None})
 return {'total':len(rows),'solved':sum(x['prediction'] is not None for x in rows),'correct':sum(x['passed'] for x in rows),'wrong':sum(x['prediction'] is not None and not x['passed'] for x in rows),'failures':[x for x in rows if not x['passed']]}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--rounds',type=int,default=100);p.add_argument('--per-domain',type=int,default=50);p.add_argument('--seed',type=int,default=900000);a=p.parse_args();root=a.root.resolve();d=root/'.evo/campaign-100-tools';d.mkdir(parents=True,exist_ok=True);records=[];all_fail=[]
 for r in range(1,a.rounds+1):
  seed=a.seed+r;de=eval_cases(gen_date(seed,a.per_domain)['cases'],solve_date);lo=eval_cases(gen_logic(seed,a.per_domain)['cases'],solve_logic);rec={'round':r,'seed':seed,'date':{k:v for k,v in de.items() if k!='failures'},'logic':{k:v for k,v in lo.items() if k!='failures'}};records.append(rec)
  for domain,result in [('date',de),('logic',lo)]:
   for x in result['failures']:all_fail.append({'round':r,'seed':seed,'domain':domain,**x})
  (d/'state.json').write_text(json.dumps({'round':r,'status':'running','failures':len(all_fail)},indent=2)+'\n')
 summary={'rounds':a.rounds,'per_domain':a.per_domain,'total_tasks':a.rounds*a.per_domain*2,'date_correct':sum(x['date']['correct'] for x in records),'logic_correct':sum(x['logic']['correct'] for x in records),'wrong_answers':sum(x['date']['wrong']+x['logic']['wrong'] for x in records),'fallbacks':sum((x['date']['total']-x['date']['solved'])+(x['logic']['total']-x['logic']['solved']) for x in records),'failure_count':len(all_fail),'status':'complete','completed_at':time.strftime('%Y-%m-%dT%H:%M:%S')};(d/'rounds.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records));(d/'failures.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in all_fail),encoding='utf-8');(d/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(d/'state.json').write_text(json.dumps({'round':a.rounds,'status':'complete','failures':len(all_fail)},indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
