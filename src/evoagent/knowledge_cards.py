from __future__ import annotations
import argparse, hashlib, json, random, re, time
from pathlib import Path

def sentences(text): return [x.strip() for x in re.split(r'(?<=[.!?])\s+',text or '') if len(x.strip())>30]
def pick(ss,words): return next((s for s in ss if any(w in s.lower() for w in words)),None)
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--seed',type=int,default=20260724);a=p.parse_args();root=a.root.resolve();manifest=json.loads((root/'.evo/learning/curriculum-last.json').read_text(encoding='utf-8-sig')); cards=[]
 for topic in manifest['topics']:
  if topic['status']!='ok':continue
  run=json.loads(Path(topic['run']).read_text(encoding='utf-8-sig'))
  for paper in run['papers']:
   ss=sentences(paper.get('abstract','')); pid=str(paper.get('paper_id','')); card={'card_id':hashlib.sha256((topic['id']+pid).encode()).hexdigest()[:16],'topic':topic['id'],'paper_id':pid,'title':paper.get('title'),'year':paper.get('year'),'authors':paper.get('authors'),'source':'peS2o','retrieval_score':paper.get('score'),'problem':pick(ss,['problem','challenge','limitation','lack','unclear']) or (ss[0] if ss else ''),'method':pick(ss,['we propose','we introduce','we present','our method','framework']),'result':pick(ss,['result','outperform','improve','demonstrate','show that','find that']),'limitations':pick(ss,['limitation','however','remain','future work']),'abstract':paper.get('abstract',''),'status':'evidence_only','verified_by':['source_metadata'],'created_at':time.strftime('%Y-%m-%dT%H:%M:%S')};cards.append(card)
 out=root/'.evo/learning/knowledge/cards.jsonl';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cards),encoding='utf-8')
 rng=random.Random(a.seed); pool=[c for c in cards if len(c['abstract'])>200 and c['title']]; rng.shuffle(pool); chosen=pool[:min(24,len(pool))]; questions=[];keys=[]
 for i,c in enumerate(chosen):
  distract=[x['title'] for x in pool if x['topic']==c['topic'] and x['card_id']!=c['card_id']][:3]
  if len(distract)<3:distract += [x['title'] for x in pool if x['card_id']!=c['card_id'] and x['title'] not in distract][:3-len(distract)]
  opts=distract+[c['title']];rng.shuffle(opts); qid=f'paper-{i+1:03d}'; excerpt=' '.join(sentences(c['abstract'])[:2])[:900];questions.append({'id':qid,'topic':c['topic'],'question':f'Which paper title best matches this abstract excerpt?\n{excerpt}','options':{chr(65+j):v for j,v in enumerate(opts)}});keys.append({'id':qid,'answer':chr(65+opts.index(c['title'])),'paper_id':c['paper_id'],'card_id':c['card_id']})
 pub=root/'benchmarks/learning/public/questions.json';key=root/'benchmarks/learning/hidden/answer-key.json';pub.parent.mkdir(parents=True,exist_ok=True);key.parent.mkdir(parents=True,exist_ok=True);pub.write_text(json.dumps({'seed':a.seed,'questions':questions},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');key.write_text(json.dumps({'dataset_sha256':hashlib.sha256(pub.read_bytes()).hexdigest(),'answers':keys},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'cards':len(cards),'questions':len(questions),'cards_file':str(out),'questions_file':str(pub),'key_file':str(key)},ensure_ascii=False))
if __name__=='__main__':main()
