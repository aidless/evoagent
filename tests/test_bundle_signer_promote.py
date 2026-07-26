import subprocess,sys,os,json,tempfile,unittest
from pathlib import Path
class BundleSignerPromoteTests(unittest.TestCase):
 def run_promote(self,*args):
  env=os.environ.copy();env['PYTHONPATH']=r'E:\self-evolving-agent\src'
  return subprocess.run([sys.executable,'-m','evoagent.bundle_signer','promote',*args],env=env,capture_output=True,text=True)
 def test_unsigned_active_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);bundles=p/'b.json';signatures=p/'s.json';trusted=p/'t';trusted.mkdir();active=p/'a.txt'
   active.write_text('unsigned-bundle@1')
   bundles.write_text(json.dumps({'bundles':{'unsigned-bundle@1':{'bundle_id':'unsigned-bundle@1','sha256':'abc','manifest':{'name':'x','active_skills':{},'files':{}},'created_at':'2026-07-24'}}}))
   r=self.run_promote('--bundles',str(bundles),'--signatures',str(signatures),'--trusted',str(trusted),'--active',str(active))
   self.assertNotEqual(r.returncode,0)
   combined=r.stdout+r.stderr
   self.assertTrue('missing_signature' in combined or 'rejected' in combined or 'reason' in combined)
 def test_missing_active_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);bundles=p/'b.json';signatures=p/'s.json';trusted=p/'t';trusted.mkdir()
   r=self.run_promote('--bundles',str(bundles),'--signatures',str(signatures),'--trusted',str(trusted),'--active',str(p/'missing.txt'))
   self.assertNotEqual(r.returncode,0)
   self.assertIn('active_file_missing',r.stdout+r.stderr)
 def test_unknown_active_id_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);bundles=p/'b.json';signatures=p/'s.json';trusted=p/'t';trusted.mkdir();active=p/'a.txt';active.write_text('ghost@1')
   bundles.write_text(json.dumps({'bundles':{}}))
   r=self.run_promote('--bundles',str(bundles),'--signatures',str(signatures),'--trusted',str(trusted),'--active',str(active))
   self.assertNotEqual(r.returncode,0);self.assertIn('active_not_in_registry',r.stdout)
 def test_signed_active_passes(self):
  from evoagent.signing import SignatureRegistry,generate_keypair,sign_bundle
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);bundles=p/'b.json';signatures=p/'s.json';trusted=p/'t';trusted.mkdir();active=p/'a.txt'
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat,PrivateFormat,NoEncryption
   priv,pub=generate_keypair();Path(p/'t'/'ci.pub').write_bytes(pub);(p/'k.bin').write_bytes(priv)
   active.write_text('signed-bundle@1')
   bundles.write_text(json.dumps({'bundles':{'signed-bundle@1':{'bundle_id':'signed-bundle@1','sha256':'abc','manifest':{'name':'x','active_skills':{},'files':{}},'created_at':'2026-07-24'}}}))
   from datetime import datetime,timezone,timedelta
   env=sign_bundle(json.loads(bundles.read_text())['bundles']['signed-bundle@1'],priv,'ci',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
   SignatureRegistry(signatures,{'ci':pub}).add(env,json.loads(bundles.read_text())['bundles']['signed-bundle@1'])
   r=self.run_promote('--bundles',str(bundles),'--signatures',str(signatures),'--trusted',str(trusted),'--active',str(active))
   self.assertEqual(r.returncode,0)
   self.assertIn('"promoted": true',r.stdout)
 def test_signed_bundle_with_changed_manifest_file_is_rejected(self):
  from evoagent.signing import SignatureRegistry,generate_keypair,sign_bundle
  from hashlib import sha256
  from datetime import datetime,timezone,timedelta
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);trusted=p/'t';trusted.mkdir();active=p/'a.txt';bundles=p/'b.json';signatures=p/'s.json';artifact=p/'artifact.py'
   artifact.write_text('safe')
   priv,pub=generate_keypair();(trusted/'ci.pub').write_bytes(pub);active.write_text('b@1')
   bundle={'bundle_id':'b@1','sha256':'abc','manifest':{'name':'x','active_skills':{},'files':{'sources':{str(artifact):sha256(artifact.read_bytes()).hexdigest()}}},'created_at':'2026'}
   bundles.write_text(json.dumps({'bundles':{'b@1':bundle}}))
   env=sign_bundle(bundle,priv,'ci',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat());SignatureRegistry(signatures,{'ci':pub}).add(env,bundle)
   artifact.write_text('tampered')
   r=self.run_promote('--bundles',str(bundles),'--signatures',str(signatures),'--trusted',str(trusted),'--active',str(active))
   self.assertNotEqual(r.returncode,0);self.assertIn('manifest_files_changed',r.stdout)
if __name__=='__main__':unittest.main()
