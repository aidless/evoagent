import unittest
from evoagent.research_agent import validate
class CitationGateTests(unittest.TestCase):
 def setUp(self):self.p=[{'paper_id':'2501.00001'},{'paper_id':'2501.00002'}]
 def test_accepts_only_supplied_ids(self):self.assertTrue(validate('Claim [2501.00001].',self.p)['valid'])
 def test_rejects_unknown_id(self):
  r=validate('Claim [9999.99999].',self.p);self.assertFalse(r['valid']);self.assertEqual(r['unknown'],['9999.99999'])
 def test_rejects_missing_citations(self):self.assertFalse(validate('Unsupported claim.',self.p)['valid'])
if __name__=='__main__':unittest.main()
