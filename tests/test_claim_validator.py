import unittest
from evoagent.benchmark_registry import CSV
from evoagent.claim_validator import cited_claims, validate_answer

# test_wrong_number_rejected resolves numbers through the benchmark registry,
# which is not committed. The rest of this class is registry-free and still runs.
HAVE_REGISTRY=CSV.exists()

class ClaimValidatorTests(unittest.TestCase):
 def setUp(self):self.p=[{'paper_id':'p1','title':'Self-verification on ARC','abstract':'Self-verification improves Qwen-7B accuracy on ARC-Challenge but degrades on TruthfulQA.'}]
 def test_supported_claim(self):self.assertTrue(validate_answer('Self-verification improves Qwen-7B on ARC-Challenge [p1].',self.p)['all_supported'])
 @unittest.skipUnless(HAVE_REGISTRY,f'benchmark registry not available at {CSV}')
 def test_wrong_number_rejected(self):self.assertFalse(validate_answer('Accuracy improves by 99% on ARC-Challenge [p1].',self.p)['all_supported'])
 def test_unrelated_claim_rejected(self):self.assertFalse(validate_answer('The method reduces GPU memory for image diffusion [p1].',self.p)['all_supported'])
 def test_evidence_span_is_returned(self):
  r=validate_answer('Self-verification improves Qwen-7B on ARC-Challenge [p1].',self.p);self.assertIn('ARC-Challenge',r['claims'][0]['best_evidence']['evidence_span'])
 def test_contrastive_sentence_is_atomic(self):
  rows=cited_claims('It improves ARC but degrades TruthfulQA [p1].');self.assertEqual(len(rows),2)
 def test_direction_conflict_rejected(self):
  self.assertFalse(validate_answer('Self-verification improves TruthfulQA [p1].',[{'paper_id':'p1','abstract':'Self-verification degrades performance on TruthfulQA.'}])['all_supported'])
 def test_wrong_benchmark_rejected(self):
  self.assertFalse(validate_answer('Self-verification improves Qwen-7B accuracy on GSM8K [p1].',self.p)['all_supported'])
 def test_wrong_model_rejected(self):
  self.assertFalse(validate_answer('Self-verification improves Llama accuracy on ARC-Challenge [p1].',self.p)['all_supported'])
 def test_structured_fields_exposed(self):
  r=validate_answer('Self-verification improves Qwen-7B accuracy on ARC-Challenge [p1].',self.p);f=r['claims'][0]['best_evidence'];self.assertTrue(f['structured_fields_ok']);self.assertIn('arc-challenge',f['claim_fields']['benchmarks'])
if __name__=='__main__':unittest.main()
