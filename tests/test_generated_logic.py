import unittest
from evoagent.logic_generator import generate
from evoagent.reasoning_tools import solve_logic
class GeneratedLogicPropertyTests(unittest.TestCase):
 def test_multiple_seeds_are_exact_when_solved(self):
  for seed in (7,101,2026072401):
   data=generate(seed,60)
   preds=[solve_logic(x['input']) for x in data['cases']]
   self.assertTrue(all(p is not None for p in preds))
   self.assertTrue(all(f'({p})'==x['target'] for p,x in zip(preds,data['cases'])))
if __name__=='__main__':unittest.main()
