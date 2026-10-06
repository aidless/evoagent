import os,unittest
from pathlib import Path
from evoagent.benchmark_registry import CSV,load,query,validate_fact,validate_quantitative_claim

# The 155-row benchmarks.csv lives in a personal knowledge base and was never
# committed. Point EVO_BENCHMARKS_CSV at a copy to exercise these locally.
HAVE_REGISTRY=CSV.exists()
MISSING_REGISTRY_REASON=f'benchmark registry not available at {CSV} (set EVO_BENCHMARKS_CSV)'

@unittest.skipUnless(HAVE_REGISTRY,MISSING_REGISTRY_REASON)
class BenchmarkRegistryTests(unittest.TestCase):
 def test_registry_has_155_rows(self):self.assertEqual(len(load()),155)
 def test_exact_fact(self):self.assertTrue(validate_fact('Llama 3.1 405B Instruct','MMLU',87.3,'5-shot')['valid'])
 def test_wrong_score(self):self.assertFalse(validate_fact('Llama 3.1 405B Instruct','MMLU',97.3,'5-shot')['valid'])
 def test_wrong_protocol(self):self.assertFalse(validate_fact('Llama 3.1 405B Instruct','MMLU',87.3,'0-shot')['valid'])
 def test_claim_lookup(self):self.assertTrue(validate_quantitative_claim('Llama 3.1 405B Instruct scores 87.3% on MMLU.')['valid'])
if __name__=='__main__':unittest.main()
