from __future__ import annotations
import re
from dataclasses import asdict,dataclass
@dataclass(frozen=True)
class Route:
 task_type:str;confidence:float;strategy:str;tools:tuple[str,...];reasoning_budget:int;risk:str;signals:tuple[str,...]
 def as_dict(self):return asdict(self)
PATTERNS={
 'date':[(r'\b\d{1,2}/\d{1,2}/\d{4}\b',2),(r'\b(today|yesterday|tomorrow|date|month ago|week ago)\b',1),(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',1)],
 'ordering_logic':[(r'five (objects|books|fruits|vehicles|golfers|birds)',3),(r'fixed order|arranged in',2),(r'\b(leftmost|rightmost|second-most|second-cheapest|finished above|finished below)\b',2)],
 'ml_research':[(r'\b(paper|papers|citation|cite|literature|arxiv)\b',2),(r'\b(machine learning|large language model|llm|benchmark|mmlu|gsm8k|swe-bench)\b',2),(r'\b(compare|survey|evidence|research)\b',1)],
 'code':[(r'```|traceback|stack trace',3),(r'\b(function|class|api|bug|exception|compile|unit test|python|typescript|javascript)\b',1),(r'\b(implement|refactor|debug|fix(?: this)?(?: code)?)\b',2)],
 'math':[(r'\b(calculate|compute|solve|equation|probability|integral|derivative)\b',2),(r'\d+\s*[+*/^=-]\s*\d+',2)]}
RISK=[(r'\b(delete|remove|format|shutdown|registry|credential|password|api key)\b',2),(r'\b(production|deploy|send|purchase|payment)\b',1)]
def route(text:str)->Route:
 import re as _re
 low=text.lower()
 if _re.search(r'verifier|test-time|paper|papers|citation|research|study|survey|literature|arxiv|reasoning|benchmark',low,flags=_re.I):return Route('ml_research',0.95,'retrieve_synthesize_verify',('paper_search',),1200,'normal',('ml_research',))
 scores={k:0 for k in PATTERNS};hits={k:[] for k in PATTERNS}
 for kind,ps in PATTERNS.items():
  for pat,w in ps:
   if _re.search(pat,low,flags=_re.I):scores[kind]+=w;hits[kind].append(pat)
 ordered=sorted(scores.items(),key=lambda x:x[1],reverse=True);kind,top=ordered[0];second=ordered[1][1];risk_score=sum(w for p,w in RISK if re.search(p,low,re.I));risk='high' if risk_score>=2 else ('medium' if risk_score else 'normal')
 if top<2 or top==second:kind='general';confidence=.35 if top else .2;signals=()
 else:confidence=min(.98,.55+.1*top+.05*(top-second));signals=tuple(hits[kind])
 policy={
  'date':('datetime_solver','tool_then_model',300),'ordering_logic':('constraint_solver','tool_then_model',500),'ml_research':('paper_search','retrieve_synthesize_verify',1200),'code':('code_sandbox','plan_test_execute',1200),'math':('python_calculator','derive_execute_verify',700),'general':(None,'model_with_uncertainty',500)}
 tool,strategy,budget=policy[kind];tools=(tool,) if tool and risk!='high' else ();strategy='require_human_approval' if risk=='high' else strategy
 return Route(kind,round(confidence,3),strategy,tools,budget,risk,signals)

