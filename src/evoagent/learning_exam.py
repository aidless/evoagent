from __future__ import annotations
import argparse,json,os,re,time,urllib.request
from pathlib import Path

def ask(endpoint,model,prompt,timeout):
 body=json.dumps({'model':model,'temperature':0,'max_tokens':12,'messages':[{'role':'system','content':'Answer multiple choice questions with exactly one letter: A, B, C, or D.'},{'role':'user','content':prompt}]}).encode();req=urllib.request.Request(endpoint.rstrip('/')+'/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer local'});return json.load(urllib.request.urlopen(req,timeout=timeout))['choices'][0]['message']['content']
def toks(s):return set(re.findall(r'[a-z0-9]+',(s or '').lower()))
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--mode',choices=['closed','rag'],required=True);p.add_argument('--limit',type=int,default=0);p.add_argument('--endpoint',default=os.getenv('EVO_MODEL_ENDPOINT','http://127.0.0.1:1234/v1'));p.add_argument('--model',default=os.getenv('EVO_MODEL','local-model'));p.add_argument('--timeout',type=int,default=180);a=p.parse_args();root=a.root.resolve();qs=json.loads((root/'benchmarks/learning/public/questions.json').read_text(encoding='utf-8-sig'))['questions'];keys={x['id']:x['answer'] for x in json.loads((root/'benchmarks/learning/hidden/answer-key.json').read_text(encoding='utf-8-sig'))['answers']};cards=[json.loads(x) for x in (root/'.evo/learning/knowledge/cards.jsonl').read_text(encoding='utf-8').splitlines()];rows=[]
 for q in qs[:a.limit or None]:
  prompt=q['question']+'\n'+'\n'.join(f'{k}. {v}' for k,v in q['options'].items())
  if a.mode=='rag':
   qt=toks(q['question']);best=max(cards,key=lambda c:len(qt&toks(c['abstract'])));prompt='Retrieved evidence:\nTitle: '+best['title']+'\nAbstract: '+best['abstract'][:1200]+'\n\n'+prompt
  try:out=ask(a.endpoint,a.model,prompt,a.timeout);m=re.search(r'\b([A-D])\b',out.upper());pred=m.group(1) if m else None
  except Exception as e:out=f'{type(e).__name__}: {e}';pred=None
  rows.append({'id':q['id'],'prediction':pred,'answer':keys[q['id']],'passed':pred==keys[q['id']],'output':out})
 result={'mode':a.mode,'score':sum(x['passed'] for x in rows)/len(rows) if rows else 0,'passed':sum(x['passed'] for x in rows),'total':len(rows),'model':a.model,'rows':rows,'at':time.strftime('%Y-%m-%dT%H:%M:%S')};out=root/'.evo/learning/exams'/f'{time.strftime("%Y%m%d-%H%M%S")}-{a.mode}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'mode':a.mode,'score':result['score'],'passed':result['passed'],'total':result['total'],'saved':str(out)},ensure_ascii=False))
if __name__=='__main__':main()
