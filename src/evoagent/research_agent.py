from __future__ import annotations
import argparse,json,os,re,time,urllib.request
from pathlib import Path
from .knowledge import search
from .claim_validator import validate_answer

def ask(endpoint,model,prompt,timeout=240):
 body=json.dumps({'model':model,'temperature':0,'max_tokens':900,'messages':[{'role':'system','content':'You are a cautious machine-learning research analyst. Use only supplied evidence. Cite claims with square-bracket paper IDs.'},{'role':'user','content':prompt}]}).encode();req=urllib.request.Request(endpoint.rstrip('/')+'/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer local'});return json.load(urllib.request.urlopen(req,timeout=timeout))['choices'][0]['message']['content']
def build(question,papers):
 evidence=[]
 for p in papers:evidence.append(f"ID: {p.get('paper_id')}\nTITLE: {p.get('title')}\nYEAR: {p.get('year')}\nABSTRACT: {(p.get('abstract') or '')[:1800]}")
 return f'''Research question: {question}\n\nEvidence:\n\n'''+"\n\n---\n\n".join(evidence)+'''\n\nWrite a concise research brief with: Findings, Conflicting/conditional evidence, Practical implications, Limitations. Every substantive claim must cite one or more supplied IDs like [2501.12345]. Do not invent citations or claim access to full text.'''
def validate(answer,papers):
 allowed={str(p.get('paper_id')) for p in papers};cited=set(re.findall(r'\[([^\[\]]+)\]',answer));unknown=sorted(cited-allowed);return {'valid':bool(cited) and not unknown,'cited':sorted(cited),'unknown':unknown,'allowed_count':len(allowed),'citation_count':len(cited)}
def main():
 p=argparse.ArgumentParser();p.add_argument('question');p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('-n',type=int,default=8);p.add_argument('--year-min',type=int,default=2024);p.add_argument('--endpoint',default=os.getenv('EVO_MODEL_ENDPOINT','http://127.0.0.1:1234/v1'));p.add_argument('--model',default=os.getenv('EVO_MODEL','local-model'));a=p.parse_args();papers=search(a.question,a.n,a.year_min);prompt=build(a.question,papers);answer=ask(a.endpoint,a.model,prompt);check=validate(answer,papers);claims=validate_answer(answer,papers) if check['valid'] else {'all_supported':False}
 if not check['valid'] or not claims['all_supported']:
  answer='\n'.join(f"- {x.get('title')}: {(x.get('abstract') or '').split('.')[0]}. [{x.get('paper_id')}]" for x in papers);check=validate(answer,papers);check['fallback']='extractive';claims=validate_answer(answer,papers,threshold=.10)
 result={'question':a.question,'answer':answer,'validation':check,'claim_validation':claims,'evidence':papers,'model':a.model,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'status':'grounded' if check['valid'] and claims['all_supported'] else 'evidence_only'};out=a.root.resolve()/'.evo/learning/research-briefs'/f'{time.strftime("%Y%m%d-%H%M%S")}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'citations':check['citation_count'],'unknown':check['unknown'],'saved':str(out),'answer':answer},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
