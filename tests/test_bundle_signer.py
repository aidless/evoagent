import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64,subprocess,sys
from evoagent.signing import generate_keypair,verify_envelope
class BundleSignerCLITests(unittest.TestCase):
 def setUp(self):self.t=self.p=Path
 def _run(self,args):
  _root=Path(__file__).resolve().parents[1];_env=__import__('os').environ.copy();_env['PYTHONPATH']=str(_root/'src')
  return subprocess.check_call([sys.executable,'-m','evoagent.bundle_signer',*args],cwd=str(_root),env=_env)
 def test_request_payload_matches_canonical(self):
  bundle={'bundle_id':'b@1','sha256':'h'}
  out=Path(self.t.mkdtemp()) if hasattr(self.t,'mkdtemp') else Path(__import__('tempfile').mkdtemp())
  (out/'b.json').write_text(__import__('json').dumps(bundle))
  self._run(['request','--bundle',str(out/'b.json'),'--signer','ci-release','--output',str(out/'req.json')])
  req=__import__('json').loads((out/'req.json').read_text())
  self.assertEqual(req['bundle_id'],'b@xyz' if False else 'b@1')
 def test_signed_envelope_passes_verify(self):
  import tempfile
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);bundle={'bundle_id':'b@1','sha256':'h'};(p/'b.json').write_text(__import__('json').dumps(bundle))
   priv,pub=generate_keypair();(p/'k.bin').write_bytes(priv)
   self._run(['sign','--bundle',str(p/'b.json'),'--private-key',str(p/'k.bin'),'--envelope',str(p/'env.json'),'--signer','ci-release','--validity-days','30'])
   env=__import__('json').loads((p/'env.json').read_text())
   self.assertTrue(verify_envelope(env,bundle,{'ci-release':pub})['valid'])
if __name__=='__main__':unittest.main()
