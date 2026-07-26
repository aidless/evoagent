import tempfile,unittest
from pathlib import Path
from evoagent.version_registry import VersionRegistry
class VersionRegistryTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=VersionRegistry(Path(self.t.name)/'registry.json');self.r.register('v1','agent')
 def tearDown(self):self.t.cleanup()
 def test_experimental_to_provisional(self):self.r.transition('v1','provisional',{'development_passed':True,'rollback_available':True});self.assertEqual(self.r.get('v1')['level'],'provisional')
 def test_missing_evidence_rejected(self):
  with self.assertRaisesRegex(ValueError,'missing evidence'):self.r.transition('v1','provisional',{})
 def test_level_skip_rejected(self):
  with self.assertRaisesRegex(ValueError,'skipping'):self.r.transition('v1','stable',{'statistical_passed':True})
 def test_stable_requires_hidden_and_statistics(self):
  self.r.transition('v1','provisional',{'development_passed':True,'rollback_available':True})
  with self.assertRaises(ValueError):self.r.transition('v1','stable',{'statistical_passed':True})
  self.r.transition('v1','stable',{'statistical_passed':True,'hidden_passed':True,'safety_passed':True,'rollback_available':True,'bundle_signature_valid':True});self.assertEqual(self.r.get('v1')['level'],'stable')
 def test_production_requires_human(self):
  self.r.transition('v1','provisional',{'development_passed':True,'rollback_available':True});self.r.transition('v1','stable',{'statistical_passed':True,'hidden_passed':True,'safety_passed':True,'rollback_available':True,'bundle_signature_valid':True})
  with self.assertRaises(ValueError):self.r.transition('v1','production',{'shadow_passed':True,'safety_passed':True,'rollback_available':True})
 def test_downgrade_allowed_and_audited(self):
  self.r.transition('v1','provisional',{'development_passed':True,'rollback_available':True});e=self.r.transition('v1','experimental',reason='regression');self.assertEqual(e['to'],'experimental');self.assertEqual(self.r.get('v1')['level'],'experimental')
 def test_annotation_updates_evidence_without_level_change(self):
  self.r.annotate('v1',{'benchmark_confirmed':False,'evidence_status':'benchmark-unconfirmed'},reason='real reassessment pending')
  self.assertEqual(self.r.get('v1')['level'],'experimental')
  self.assertFalse(self.r.get('v1')['evidence']['benchmark_confirmed'])
  self.assertEqual(self.r.data['history'][-1]['action'],'annotate')

if __name__=='__main__':unittest.main()
