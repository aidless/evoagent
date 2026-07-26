import tempfile,unittest
from pathlib import Path
from evoagent.attestation import AttestationRegistry,hash_file,hash_paths
class AttestationTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.f=self.p/'x.py';self.f.write_text('x=1\n');self.r=AttestationRegistry(self.p/'a.json')
 def tearDown(self):self.t.cleanup()
 def test_file_hash_changes(self):
  a=hash_file(self.f);self.f.write_text('x=2\n');self.assertNotEqual(a,hash_file(self.f))
 def test_bundle_hash_is_stable(self):self.assertEqual(hash_paths([self.f])[0],hash_paths([self.f])[0])
 def test_missing_attestation(self):self.assertFalse(self.r.verify('none')['valid'])
 def test_tamper_detected(self):
  import evoagent.router as router
  self.r.attest('router@1','evoagent.router:route',tests=[self.f]);self.assertTrue(self.r.verify('router@1')['valid']);self.f.write_text('changed');v=self.r.verify('router@1');self.assertFalse(v['valid']);self.assertEqual(v['reason'],'artifact_changed')
 def test_unapproved_entrypoint_rejected(self):
  with self.assertRaises(ValueError):self.r.attest('x@1','os:path')
if __name__=='__main__':unittest.main()
