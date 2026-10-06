from __future__ import annotations
import os
import hashlib,json,random
from pathlib import Path
ITEMS=['amber','birch','cedar','denim','elm']
def generate(seed=2026072401,n=200):
 rng=random.Random(seed);rows=[]
 for i in range(n):
  order=ITEMS[:];rng.shuffle(order);kind='spatial' if i%2==0 else 'tournament';statements=[]
  # A complete chain has a unique ground-truth order; vary direction and sentence order.
  for j in range(4):
   a,b=order[j],order[j+1]
   if kind=='spatial':
    statements.append(f'The {a} token is to the left of the {b} token.' if rng.random()<.5 else f'The {b} token is to the right of the {a} token.')
   else:
    statements.append(f'{a} finished above {b}.' if rng.random()<.5 else f'{b} finished below {a}.')
  rng.shuffle(statements);target_pos=rng.randrange(5);target=order[target_pos];labels_sp=['leftmost','second from the left','third from the left','second from the right','rightmost'];labels_t=['first','second','third','fourth','last'];label=(labels_sp if kind=='spatial' else labels_t)[target_pos]
  options=[]
  for x in ITEMS: options.append(f'The {x} token is the {label}' if kind=='spatial' else f'{x} finished {label}')
  rng.shuffle(options);answer=chr(65+next(k for k,v in enumerate(options) if (v.startswith('The '+target+' ') if kind=='spatial' else v.startswith(target+' '))))
  stem=('Five tokens are arranged in a fixed order. ' if kind=='spatial' else 'Five competitors have distinct finishing ranks. ')+' '.join(statements);text=stem+'\nOptions:\n'+'\n'.join(f'({chr(65+k)}) {v}' for k,v in enumerate(options));rows.append({'id':f'gen-{i+1:04d}','kind':kind,'input':text,'target':f'({answer})'})
 return {'version':1,'seed':seed,'generator':'independent_permutation_v1','cases':rows}
def main():
 root=Path(os.environ.get('EVO_WORKSPACE')or Path(__file__).resolve().parents[2]);data=generate();pub=root/'benchmarks/generated_logic/questions.json';key=root/'benchmarks/generated_logic/hidden-key.json';pub.parent.mkdir(parents=True,exist_ok=True);questions={'version':1,'seed':data['seed'],'cases':[{'id':x['id'],'kind':x['kind'],'input':x['input']} for x in data['cases']]};pub.write_text(json.dumps(questions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');key.write_text(json.dumps({'questions_sha256':hashlib.sha256(pub.read_bytes()).hexdigest(),'answers':[{'id':x['id'],'target':x['target']} for x in data['cases']]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(pub,key)
if __name__=='__main__':main()
