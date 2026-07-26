import unittest
from datetime import datetime,timezone,timedelta
from evoagent.signing import generate_keypair,sign_bundle
from evoagent.multisig import verify_multisig
class MultiSigTests(unittest.TestCase):
 def setUp(self):
  self.bundle={'bundle_id':'b@1','sha256':'abc'}
  self.privs={};self.pubs={}
  for s in ('alpha','beta','gamma'):
   p,q=generate_keypair();self.privs[s]=p;self.pubs[s]=q
  self.envelopes=[sign_bundle(self.bundle,self.privs[s],s,(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()) for s in ('alpha','beta','gamma')]
 def test_quorum_2_of_3_passes(self):
  r=verify_multisig(self.envelopes,self.bundle,self.pubs,required_signers={'alpha','beta'});self.assertTrue(r['valid']);self.assertEqual(r['valid_count'],3)
 def test_quorum_missing_gamma_fails(self):
  r=verify_multisig(self.envelopes,self.bundle,self.pubs,required_signers={'alpha','delta'});self.assertFalse(r['valid']);self.assertEqual(r['reason'],'required_signers_missing')
 def test_expired_signature_excluded(self):
  env=sign_bundle(self.bundle,self.privs['alpha'],'alpha',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat());r=verify_multisig([env]+self.envelopes[1:],self.bundle,self.pubs,required_signers={'alpha','beta'});self.assertFalse(r['valid'])
 def test_unknown_signer_excluded(self):
  r=verify_multisig(self.envelopes+[{'bundle_id':'b@1','bundle_sha256':'abc','signer':'unknown','signed_at':datetime.now(timezone.utc).isoformat(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'signature':'AAAA','algorithm':'Ed25519'}],self.bundle,self.pubs,required_signers={'alpha','beta'});self.assertTrue(r['valid']);self.assertEqual(r['valid_count'],3)
if __name__=='__main__':unittest.main()
