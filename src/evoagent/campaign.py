from __future__ import annotations
import argparse, hashlib, json, os, random, subprocess, sys, time
from pathlib import Path

CLAUSES=[
"Translate every condition into explicit facts before solving.",
"For arithmetic, form equations, track units, and recompute the final number.",
"For dates, identify the reference date and apply offsets one at a time.",
"For ordering logic, construct a complete ordered list satisfying every constraint.",
"Derive a candidate answer and then verify it independently.",
"Try to find a counterexample that would make the candidate answer invalid.",
"Substitute the result back into the original conditions.",
"Check arithmetic signs, option letters, units, and off-by-one errors.",
"If verification fails, discard the answer and solve again using another method.",
"Keep reasoning focused and finish with the exact requested number or option."
]
PREFIXES=["You are a rigorous problem solver.","Solve with precision and skepticism.","Act as an independent solver and verifier."]

def save(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def make(rng):
    clauses=rng.sample(CLAUSES,rng.randint(2,5)); prompt=rng.choice(PREFIXES)+' '+' '.join(clauses)
    return {'system_prompt':prompt,'prompt_strategy':'campaign_v1'}
def cid(c): return hashlib.sha256(c['system_prompt'].encode()).hexdigest()[:12]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=Path.cwd()); ap.add_argument('--rounds',type=int,default=1000); ap.add_argument('--checkpoint',type=int,default=100); ap.add_argument('--seed',type=int,default=1000); a=ap.parse_args()
    root=a.root.resolve(); d=root/'.evo/campaign-1000'; d.mkdir(parents=True,exist_ok=True); statep=d/'state.json'; log=d/'progress.jsonl'; rng=random.Random(a.seed)
    state=json.loads(statep.read_text(encoding='utf-8')) if statep.exists() else {'round':0,'seen':{},'evaluations':[],'status':'running'}
    # Reproduce RNG sequence on resume.
    for _ in range(state['round']): make(rng)
    with log.open('a',encoding='utf-8') as lf:
      for n in range(state['round']+1,a.rounds+1):
        c=make(rng); key=cid(c); state['seen'].setdefault(key,c); state['round']=n
        if n % a.checkpoint==0:
          # Prefer concise, novel candidates; intelligence score remains the only promotion evidence.
          tested={x['candidate_id'] for x in state['evaluations']}; pool=[kv for kv in state['seen'].items() if kv[0] not in tested]; key,c=min(pool,key=lambda kv:(len(kv[1]['system_prompt']),kv[0]))
          cp=d/'candidates'/f'{n:04d}-{key}.json'; save(cp,c)
          cmd=[sys.executable,'-m','evoagent.intelligence','--root',str(root),'--candidate',str(cp),'--per-suite','1','--seed',str(a.seed+n),'--timeout','180']
          run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=900)
          try: result=json.loads(run.stdout)
          except Exception: result={'verified':False,'reason':run.stderr[-500:] or 'invalid_output'}
          record={'round':n,'candidate_id':key,'result':result,'at':time.strftime('%Y-%m-%dT%H:%M:%S')}; state['evaluations'].append(record); lf.write(json.dumps(record,ensure_ascii=False)+'\n'); lf.flush()
        if n%10==0: save(statep,state)
      state['status']='search_complete'; save(statep,state)
    print(json.dumps({'rounds':state['round'],'unique':len(state['seen']),'checkpoints':len(state['evaluations']),'status':state['status']},ensure_ascii=False))
if __name__=='__main__': main()
