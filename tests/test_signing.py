from datetime import datetime,timedelta,timezone
import tempfile,unittest
from pathlib import Path
from evoagent.signing import SignatureRegistry,generate_keypair,sign_bundle,verify_envelope
class SigningTests(unittest.TestCase):
 def setUp(self):self.priv,self.pub=generate_keypair();self.bundle={'bundle_id':'b@1','sha256':'abc'};self.exp=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();self.e=sign_bundle(self.bundle,self.priv,'ci-release',self.exp)
 def test_valid(self):self.assertTrue(verify_envelope(self.e,self.bundle,{'ci-release':self.pub})['valid'])
 def test_wrong_key(self):self.assertFalse(verify_envelope(self.e,self.bundle,{'ci-release':generate_keypair()[1]})['valid'])
 def test_tampered_bundle(self):self.assertEqual(verify_envelope(self.e,{'bundle_id':'b@1','sha256':'changed'},{'ci-release':self.pub})['reason'],'bundle_mismatch')
 def test_untrusted_signer(self):self.assertEqual(verify_envelope(self.e,self.bundle,{})['reason'],'untrusted_signer')
 def test_expired(self):
  e=sign_bundle(self.bundle,self.priv,'ci-release',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat());self.assertEqual(verify_envelope(e,self.bundle,{'ci-release':self.pub})['reason'],'signature_expired')
 def test_registry_rejects_invalid(self):
  with tempfile.TemporaryDirectory() as td:
   r=SignatureRegistry(Path(td)/'s.json',{'ci-release':generate_keypair()[1]})
   with self.assertRaises(ValueError):r.add(self.e,self.bundle)
if __name__=='__main__':unittest.main()
