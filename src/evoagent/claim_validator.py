from __future__ import annotations
import re
from .benchmark_registry import validate_quantitative_claim
STOP=set('a an the and or of to in on for with by as is are was were be been being that this it its from can may could should would across using use into than then their our we they model models paper study results result'.split())
DIR={'improve','improves','improved','outperform','outperforms','degrade','degrades','worse','better','increase','decrease','fail','fails','effective','ineffective'}
def tokens(s):return {x for x in re.findall(r'[a-z][a-z0-9_-]{2,}',s.lower()) if x not in STOP}
def cited_claims(answer):
 chunks=re.split(r'(?<=[.!?])\s+|\n+',answer);out=[]
 for c in chunks:
  ids=re.findall(r'\[([^\[\]]+)\]',c)
  if not ids: continue
  clean=re.sub(r'\[[^]]+\]','',c).strip()
  # Split contrastive/semicolon compounds; keep citations attached to each atom.
  parts=[x.strip(' -:') for x in re.split(r';|\bbut\b|\bhowever,?\b|\bwhile\b',clean,flags=re.I) if len(x.strip())>5]
  for part in parts or [clean]: out.append({'claim':part,'citations':ids,'source_sentence':c.strip()})
 return out

BENCHMARKS=['arc-challenge','truthfulqa','gsm8k','mmlu','mmlu-pro','gpqa','humaneval','mbpp','swe-bench','math-500','aime','bfcl']
METRICS=['accuracy','pass@1','f1','precision','recall','aurc','ece','latency','throughput']
MODELS=['qwen','qwen-7b','llama','mistral','deepseek','phi-2','phi','gemma','glm','gpt-4','gpt-4o']
def structured_fields(text):
 low=text.lower();return {'benchmarks':sorted({x for x in BENCHMARKS if x in low}),'metrics':sorted({x for x in METRICS if x in low}),'models':sorted({x for x in MODELS if x in low}),'numbers':sorted(set(re.findall(r'\b\d+(?:\.\d+)?%?\b',text))),'directions':sorted(tokens(text)&DIR)}
def claim_type(text):
 f=structured_fields(text)
 if f['numbers']:return 'quantitative'
 if f['directions'] and (f['benchmarks'] or f['metrics']):return 'comparative'
 if any(x in text.lower() for x in ('cause','leads to','results in')):return 'causal'
 return 'descriptive'
def validate_claim(claim,citations,papers,threshold=.16):
 by={str(p.get('paper_id')):p for p in papers};ct=tokens(re.sub(r'\[[^]]+\]','',claim));nums=set(re.findall(r'\b\d+(?:\.\d+)?%?\b',claim));best=None
 for cid in citations:
  p=by.get(cid)
  if not p:continue
  ev=(p.get('title') or '')+'. '+(p.get('abstract') or '');spans=[x.strip() for x in re.split(r'(?<=[.!?])\s+',ev) if x.strip()]
  for span in spans:
   et=tokens(span);over=ct&et;coverage=len(over)/max(1,len(ct));evnums=set(re.findall(r'\b\d+(?:\.\d+)?%?\b',span));num_ok=not nums or nums<=evnums;dirs=ct&DIR;dir_ok=not dirs or bool(dirs&et);cf=structured_fields(claim);ef=structured_fields(span);field_ok=all(set(cf[k])<=set(ef[k]) for k in ('benchmarks','metrics','models'));score=coverage*(1 if num_ok else .25)*(1 if dir_ok else .5)*(1 if field_ok else .25);row={'citation':cid,'score':round(score,4),'token_coverage':round(coverage,4),'numbers_ok':num_ok,'direction_ok':dir_ok,'structured_fields_ok':field_ok,'claim_type':claim_type(claim),'claim_fields':cf,'evidence_fields':ef,'evidence_terms':sorted(over),'evidence_span':span}
   if best is None or row['score']>best['score']:best=row
 registry=validate_quantitative_claim(claim) if claim_type(claim)=='quantitative' else {'applicable':False,'valid':False}
 status='supported' if best and best['score']>=threshold and best['numbers_ok'] and best['direction_ok'] and best['structured_fields_ok'] else ('partial' if best and best['score']>=threshold/2 else 'unsupported')
 if registry['applicable'] and not registry['valid']: status='unsupported'
 return {'claim':claim,'citations':citations,'status':status,'best_evidence':best,'benchmark_registry':registry}
def validate_answer(answer,papers,threshold=.16):
 rows=[validate_claim(x['claim'],x['citations'],papers,threshold) for x in cited_claims(answer)];return {'claims':rows,'supported':sum(x['status']=='supported' for x in rows),'partial':sum(x['status']=='partial' for x in rows),'unsupported':sum(x['status']=='unsupported' for x in rows),'all_supported':bool(rows) and all(x['status']=='supported' for x in rows)}

