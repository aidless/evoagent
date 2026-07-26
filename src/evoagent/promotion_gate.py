from __future__ import annotations
import math,random
from dataclasses import dataclass
from .protocol import Run

def binom_tail_two_sided(b,c):
 n=b+c
 if n==0:return 1.0
 k=min(b,c);tail=sum(math.comb(n,i) for i in range(k+1))/(2**n);return min(1.0,2*tail)
def paired_bootstrap(diffs,iterations=5000,seed=20260724,alpha=.05):
 if not diffs:return (0.0,0.0)
 rng=random.Random(seed);n=len(diffs);vals=sorted(sum(diffs[rng.randrange(n)] for _ in range(n))/n for _ in range(iterations));return vals[int((alpha/2)*iterations)],vals[min(iterations-1,int((1-alpha/2)*iterations))]
def evaluate_promotion(base:Run,cand:Run,min_gain=.02,alpha=.05,max_cost_increase=.15,max_latency_increase=.20,max_capability_drop=.01,bootstrap_iterations=5000):
 b,c=base.by_task(),cand.by_task()
 if set(b)!=set(c):return {'promote':False,'reasons':['task_set_mismatch']}
 ids=sorted(b);diffs=[c[i].score-b[i].score for i in ids];gain=sum(diffs)/len(diffs) if diffs else 0;ci=paired_bootstrap(diffs,bootstrap_iterations,alpha=alpha);discord_better=sum((not b[i].passed) and c[i].passed for i in ids);discord_worse=sum(b[i].passed and (not c[i].passed) for i in ids);p=binom_tail_two_sided(discord_better,discord_worse)
 def mean(attr,run):return sum(getattr(run[i],attr) for i in ids)/len(ids) if ids else 0
 bc,cc=mean('cost',b),mean('cost',c);bl,cl=mean('latency_s',b),mean('latency_s',c);cost_inc=(cc-bc)/bc if bc else (0 if cc==0 else float('inf'));lat_inc=(cl-bl)/bl if bl else (0 if cl==0 else float('inf'));safety=sum(c[i].safety_violations for i in ids);caps=set().union(*(o.capabilities for o in b.values()),*(o.capabilities for o in c.values()));drops={k:(sum(c[i].capabilities.get(k,0)-b[i].capabilities.get(k,0) for i in ids)/len(ids)) for k in caps};reasons=[]
 if gain<min_gain:reasons.append('gain_below_threshold')
 if ci[0]<=0:reasons.append('bootstrap_ci_not_positive')
 if p>=alpha:reasons.append('mcnemar_not_significant')
 if cost_inc>max_cost_increase:reasons.append('cost_regression')
 if lat_inc>max_latency_increase:reasons.append('latency_regression')
 if safety:reasons.append('safety_violation')
 if any(v < -max_capability_drop for v in drops.values()):reasons.append('capability_regression')
 return {'promote':not reasons,'reasons':reasons,'n':len(ids),'mean_gain':gain,'bootstrap_ci':ci,'mcnemar':{'better':discord_better,'worse':discord_worse,'p_value':p},'cost_increase':cost_inc,'latency_increase':lat_inc,'safety_violations':safety,'capability_deltas':drops}
