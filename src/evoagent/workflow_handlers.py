from __future__ import annotations
from .claim_validator import validate_answer
from .dispatcher import dispatch
from .protocol import Task
from .workflow import StepResult

def make_handlers(paper_search=None,model_fallback=None,guarded_executor=None,run_id="workflow",approval_resolver=None):
 def dispatch_h(s,ctx):
  r=dispatch(Task(s.id,'auto',s.input,{'completed':True}),model_fallback=model_fallback,paper_search=paper_search);return StepResult(s.id,r.outcome.passed,r.output,r.outcome.cost,r.outcome.latency_s,r.outcome.safety_violations,r.status,r.outcome.details)
 def search_h(s,ctx):
  fn=paper_search
  if fn is None:
   from .knowledge import search as fn
  rows=fn(s.input,8,2024);return StepResult(s.id,bool(rows),rows,status='evidence_collected' if rows else 'no_evidence')
 def synth_h(s,ctx):
  rows=ctx['retrieve'].output;answer='\n'.join(f"- {p.get('title')}: {(p.get('abstract') or '').split('.')[0]} [{p.get('paper_id')}]." for p in rows);return StepResult(s.id,bool(answer),{'answer':answer,'evidence':rows},status='extractive_synthesis')
 def verify_h(s,ctx):
  x=ctx['synthesize'].output;r=validate_answer(x['answer'],x['evidence'],threshold=.10);return StepResult(s.id,r['all_supported'],x['answer'] if r['all_supported'] else None,status='claim_supported' if r['all_supported'] else 'claim_support_failed',details={'claim_validation':r})
 def broad_search_h(s,ctx):
  fn=paper_search
  if fn is None:
   from .knowledge import search as fn
  rows=fn(s.input,20,None);return StepResult(s.id,bool(rows),rows,status='evidence_collected' if rows else 'no_evidence')
 def model_h(s,ctx):
  if not model_fallback:return StepResult(s.id,False,status='fallback_unavailable')
  x=model_fallback(str(s.input),None);return StepResult(s.id,bool(x.get('passed')),x.get('output'),status='model_fallback',details=x.get('details',{}))
 base={'dispatch':dispatch_h,'paper_search':search_h,'paper_search_broad':broad_search_h,'model_fallback':model_h,'research_synthesis':synth_h,'claim_validation':verify_h,'human_approval':lambda s,c:StepResult(s.id,False,status='human_approval_required'),'code_analysis':lambda s,c:StepResult(s.id,True,{'plan':'analyzed'},status='analysis_only'),'code_sandbox':lambda s,c:StepResult(s.id,False,status='sandbox_required'),'unit_tests':lambda s,c:StepResult(s.id,False,status='blocked_without_sandbox')}
 if guarded_executor is None:return base
 from .workflow_guard import make_guarded_handlers
 return make_guarded_handlers(base,guarded_executor,run_id,approval_resolver)
