import unittest
from evoagent.protocol import Outcome,Run,Task
from evoagent.promotion_gate import evaluate_promotion

def run(name,passes,cost=1,latency=1,safety=0,cap=1):
 return Run(name,name,'same',tuple(Outcome(str(i),p,1.0 if p else 0.0,cost,latency,safety,{'core':cap}) for i,p in enumerate(passes)))
class ProtocolTests(unittest.TestCase):
 def test_task_fingerprint_stable(self):
  a=Task('x','math',{'q':1},{'exact':True});self.assertEqual(a.fingerprint(),a.fingerprint())
 def test_task_requires_success_criteria(self):
  with self.assertRaises(ValueError):Task('x','math',{}, {})
class PromotionGateTests(unittest.TestCase):
 def setUp(self):self.base=run('b',[False]*30+[True]*70)
 def test_clear_improvement_promotes(self):
  cand=run('c',[True]*20+[False]*10+[True]*70);r=evaluate_promotion(self.base,cand,min_gain=.1,bootstrap_iterations=2000);self.assertTrue(r['promote'],r)
 def test_tiny_gain_rejected(self):
  p=[False]*29+[True]+[True]*70;r=evaluate_promotion(self.base,run('c',p),bootstrap_iterations=1000);self.assertFalse(r['promote'])
 def test_cost_regression_rejected(self):
  r=evaluate_promotion(self.base,run('c',[True]*100,cost=2),bootstrap_iterations=1000);self.assertIn('cost_regression',r['reasons'])
 def test_safety_violation_rejected(self):
  r=evaluate_promotion(self.base,run('c',[True]*100,safety=1),bootstrap_iterations=1000);self.assertIn('safety_violation',r['reasons'])
 def test_capability_regression_rejected(self):
  r=evaluate_promotion(self.base,run('c',[True]*100,cap=.5),bootstrap_iterations=1000);self.assertIn('capability_regression',r['reasons'])
 def test_task_mismatch_rejected(self):
  c=Run('c','c','other',(Outcome('other',True,1),));self.assertEqual(evaluate_promotion(self.base,c)['reasons'],['task_set_mismatch'])
if __name__=='__main__':unittest.main()
