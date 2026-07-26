import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from evoagent.signing import SignatureRegistry,generate_keypair,sign_bundle
class SigningAuditTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
 def tearDown(self):self.t.cleanup()
 def test_audit_reports_active_and_expired(self):
  priv,pub=generate_keypair();r=SignatureRegistry(self.p/'sig.json',{'ci':pub})
  bundle={'bundle_id':'b@1','sha256':'abc'}
  env1=sign_bundle(bundle,priv,'ci',(datetime.now(timezone.utc)+timedelta(days=7)).isoformat());r.add(env1,bundle)
  env2=sign_bundle({'bundle_id':'b@2','sha256':'def'},priv,'ci',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat());r.data['signatures']['b@2']={'envelope':env2,'bundle_sha256':'def'}
  a=r.audit();self.assertEqual(a['trusted_signers'],['ci']);rows={x['bundle_id']:x for x in a['signatures']};self.assertFalse(rows['b@1']['expired']);self.assertTrue(rows['b@2']['expired'])
 def test_audit_includes_history(self):
  priv,pub=generate_keypair();r=SignatureRegistry(self.p/'sig.json',{'ci':pub});r.add(sign_bundle({'bundle_id':'b@1','sha256':'abc'},priv,'ci',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()),{'bundle_id':'b@1','sha256':'abc'});self.assertGreaterEqual(len(r.audit()['history']),1)
if __name__=='__main__':unittest.main()
