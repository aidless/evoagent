import unittest
from evoagent.candidate_schema import validate_candidate
class CandidateSchemaTests(unittest.TestCase):
 def test_prompt_candidate_passes(self):self.assertTrue(validate_candidate({'system_prompt':'be careful'},'prompt')['valid'])
 def test_unknown_field_fails(self):self.assertIn('unknown_top_level:command',validate_candidate({'command':'calc.exe'},'strategy')['violations'])
 def test_nested_governance_override_fails(self):
  r=validate_candidate({'workflow':{'promotion_gate':{'enabled':False}}},'workflow');self.assertFalse(r['valid']);self.assertIn('immutable:workflow.promotion_gate',r['violations'])
 def test_evaluator_command_cannot_evolve(self):self.assertFalse(validate_candidate({'evaluator_command':'anything'},'strategy')['valid'])
if __name__=='__main__':unittest.main()
