import tempfile
import unittest
from pathlib import Path
from evoagent.key_governance import audit_key_directory
class KeyGovernanceTests(unittest.TestCase):
 def test_public_only_store_passes(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'security.pub').write_bytes(b'x');self.assertTrue(audit_key_directory(p)['valid'])
 def test_private_key_in_trust_store_fails(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'security.priv').write_bytes(b'x');r=audit_key_directory(p);self.assertFalse(r['valid']);self.assertEqual(r['reason'],'private_key_in_trust_store')
if __name__=='__main__':unittest.main()
