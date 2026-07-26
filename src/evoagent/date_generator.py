from __future__ import annotations
import calendar,hashlib,json,random
from datetime import date,timedelta
from pathlib import Path
def add_months(d,n):
 x=d.month-1+n;y=d.year+x//12;m=x%12+1;return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
def generate(seed=2026072402,n=300):
 rng=random.Random(seed);rows=[]
 for i in range(n):
  today=date(rng.randint(1990,2030),rng.randint(1,12),1);today=today.replace(day=rng.randint(1,calendar.monthrange(today.year,today.month)[1]));setup=rng.choice(['today','yesterday','tomorrow','day_before_yesterday'])
  if setup=='today':stem=f'Today is {today.month}/{today.day}/{today.year}.'
  elif setup=='yesterday':d=today-timedelta(days=1);stem=f'Yesterday was {d.month}/{d.day}/{d.year}.'
  elif setup=='tomorrow':d=today+timedelta(days=1);stem=f'Tomorrow is {d.month}/{d.day}/{d.year}.'
  else:d=today-timedelta(days=2);stem=f'The day before yesterday was {d.month}/{d.day}/{d.year}.'
  unit=rng.choice(['day','week','month','year']);amount=rng.randint(1,3);direction=rng.choice(['ago','later']);sign=-1 if direction=='ago' else 1
  if unit=='day':ans=today+timedelta(days=sign*amount)
  elif unit=='week':ans=today+timedelta(weeks=sign*amount)
  elif unit=='month':ans=add_months(today,sign*amount)
  else:ans=add_months(today,sign*12*amount)
  word='a' if amount==1 and rng.random()<.5 else ('one' if amount==1 else str(amount));q=f'What is the date {word} {unit}{"s" if amount>1 else ""} {direction} in MM/DD/YYYY?';correct=ans.strftime('%m/%d/%Y');opts={correct}
  while len(opts)<6:
   delta=rng.choice([-90,-31,-7,-2,-1,1,2,7,31,90]);opts.add((ans+timedelta(days=delta)).strftime('%m/%d/%Y'))
  opts=list(opts);rng.shuffle(opts);letter=chr(65+opts.index(correct));text=stem+' '+q+'\nOptions:\n'+'\n'.join(f'({chr(65+j)}) {v}' for j,v in enumerate(opts));rows.append({'id':f'date-{i+1:04d}','input':text,'target':f'({letter})','meta':{'setup':setup,'unit':unit,'direction':direction}})
 return {'version':1,'seed':seed,'cases':rows}
def main():
 root=Path(r'E:\self-evolving-agent');data=generate();pub=root/'benchmarks/generated_date/questions.json';key=root/'benchmarks/generated_date/hidden-key.json';pub.parent.mkdir(parents=True,exist_ok=True);q={'version':1,'seed':data['seed'],'cases':[{k:x[k] for k in ('id','input','meta')} for x in data['cases']]};pub.write_text(json.dumps(q,indent=2)+'\n');key.write_text(json.dumps({'questions_sha256':hashlib.sha256(pub.read_bytes()).hexdigest(),'answers':[{'id':x['id'],'target':x['target']} for x in data['cases']]},indent=2)+'\n');print(pub,key)
if __name__=='__main__':main()

