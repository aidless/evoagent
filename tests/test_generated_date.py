import unittest
from evoagent.date_generator import generate
from evoagent.reasoning_tools import solve_date
class GeneratedDatePropertyTests(unittest.TestCase):
 def test_multiple_seeds_exact(self):
  for seed in (11,303,2026072402):
   data=generate(seed,80)
   preds=[solve_date(x['input']) for x in data['cases']]
   self.assertTrue(all(p is not None for p in preds))
   self.assertTrue(all(f'({p})'==x['target'] for p,x in zip(preds,data['cases'])))
if __name__=='__main__':unittest.main()
