from __future__ import annotations
import argparse, json, os, random, re, urllib.request
from .reasoning_tools import solve_date, solve_logic
from .router import route
from pathlib import Path


def load_cases(root: Path, per_suite: int, seed: int):
    rng=random.Random(seed); cases=[]
    gsm=[json.loads(x) for x in (root/'benchmarks/raw/gsm8k-test.jsonl').read_text(encoding='utf-8').splitlines()]
    for x in rng.sample(gsm, min(per_suite,len(gsm))):
        answer=x['answer'].split('####')[-1].strip().replace(',','')
        cases.append(('gsm8k',x['question'],answer))
    for filename,name in [('bbh-date-understanding.json','bbh_date'),('bbh-logical-deduction-five.json','bbh_logic')]:
        rows=json.loads((root/'benchmarks/raw'/filename).read_text(encoding='utf-8'))['examples']
        for x in rng.sample(rows,min(per_suite,len(rows))): cases.append((name,x['input'],x['target'].strip()))
    return cases


def ask(endpoint, model, system, question, timeout):
    body=json.dumps({'model':model,'temperature':0,'max_tokens':512,'messages':[{'role':'system','content':system},{'role':'user','content':question+'\nReturn only the final answer.'}]}).encode()
    req=urllib.request.Request(endpoint.rstrip('/')+'/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+os.getenv('OPENAI_API_KEY','local')})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)['choices'][0]['message']['content'].strip()


def norm(x): return re.sub(r'[^a-z0-9.\-]+','',x.lower().replace(',',''))
def grade(suite, output, expected):
    if suite == 'gsm8k':
        nums = re.findall(r'-?\d+(?:,\d{3})*(?:\.\d+)?', output)
        return bool(nums) and norm(nums[-1]) == norm(expected)
    options = re.findall(r'(?:\(|\b)([A-G])\)', output.upper())
    wanted = re.search(r'[A-G]', expected.upper())
    return bool(options and wanted) and options[-1] == wanted.group(0)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path.cwd()); p.add_argument('--endpoint',default=os.getenv('EVO_MODEL_ENDPOINT','http://127.0.0.1:1234/v1')); p.add_argument('--model',default=os.getenv('EVO_MODEL','local-model')); p.add_argument('--per-suite',type=int,default=20); p.add_argument('--seed',type=int,default=20260724); p.add_argument('--timeout',type=int,default=60); p.add_argument('--candidate',type=Path); a=p.parse_args()
    system='You are a careful reasoning assistant.'
    candidate={}
    if a.candidate and a.candidate.exists(): system=json.loads(a.candidate.read_text(encoding='utf-8-sig')).get('system_prompt',system)
    cases=load_cases(a.root,a.per_suite,a.seed); rows=[]
    try:
        for suite,q,expected in cases:
            tool_answer = None
            task_route = route(q)
            if task_route.task_type == 'ordering_logic' and candidate.get('tool_router', {}).get('logical_deduction_five_objects'): tool_answer = solve_logic(q)
            elif task_route.task_type == 'date' and candidate.get('tool_router', {}).get('date_understanding', {}).get('tool') != 'disabled': tool_answer = solve_date(q)
            output = f'({tool_answer})' if tool_answer else ask(a.endpoint,a.model,system,q,a.timeout)
            ok=grade(suite,output,expected); rows.append({'suite':suite,'passed':ok,'expected':expected,'output':output})
    except Exception as e:
        result={'verified':False,'reason':type(e).__name__+': '+str(e),'endpoint':a.endpoint,'model':a.model,'total':len(cases)}
        print(json.dumps(result,ensure_ascii=False)); raise SystemExit(2)
    by={}
    for suite in sorted(set(x['suite'] for x in rows)):
        s=[x for x in rows if x['suite']==suite]; by[suite]={'passed':sum(x['passed'] for x in s),'total':len(s),'score':sum(x['passed'] for x in s)/len(s)}
    result={'verified':True,'score':sum(x['passed'] for x in rows)/len(rows),'passed':sum(x['passed'] for x in rows),'total':len(rows),'suites':by,'seed':a.seed,'model':a.model,'details':rows}
    out=a.root/'.evo'/'intelligence-last.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
