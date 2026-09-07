import unittest
from evoagent.benchmark_registry import CSV,load,query,validate_fact,validate_quantitative_claim
@unittest.skipUnless(CSV.exists(),f'private benchmark CSV not present: {CSV} (set EVO_BENCHMARK_CSV)')
class BenchmarkRegistryTests(unittest.TestCase):
 def test_registry_has_155_rows(self):self.assertEqual(len(load()),155)
 def test_exact_fact(self):self.assertTrue(validate_fact('Llama 3.1 405B Instruct','MMLU',87.3,'5-shot')['valid'])
 def test_wrong_score(self):self.assertFalse(validate_fact('Llama 3.1 405B Instruct','MMLU',97.3,'5-shot')['valid'])
 def test_wrong_protocol(self):self.assertFalse(validate_fact('Llama 3.1 405B Instruct','MMLU',87.3,'0-shot')['valid'])
 def test_claim_lookup(self):self.assertTrue(validate_quantitative_claim('Llama 3.1 405B Instruct scores 87.3% on MMLU.')['valid'])
if __name__=='__main__':unittest.main()
