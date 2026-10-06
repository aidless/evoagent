import unittest,tempfile,json
from pathlib import Path
from evoagent.model_backends import ModelSpec,ModelBackendRegistry,register_defaults
class ModelBackendTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.fake=self.p/'f.bin';self.fake.write_text('x')
 def tearDown(self):self.t.cleanup()
 def test_register_audits(self):
  r=ModelBackendRegistry(self.p/'m.json')
  r.register(ModelSpec('gguf','m1',self.fake,'fam','1B','Q4_K_M',4096,True,'apache-2.0'));self.assertIn('m1',r.list())
  a=r.audit();self.assertEqual(a['backends']['m1']['family'],'fam')
 def test_register_missing_rejected(self):
  r=ModelBackendRegistry(self.p/'m.json')
  with self.assertRaises(FileNotFoundError):r.register(ModelSpec('gguf','m1',self.p/'nope','fam','1B','Q4_K_M',4096,True,'apache-2.0'))
 def test_register_defaults_loads_available(self):
  from evoagent.model_backends import default_specs
  if not any(spec.path.exists() for spec in default_specs()):
   self.skipTest('no default model weights on this machine (HF cache / E:\\models not present)')
  r=register_defaults(self.p/'m.json');self.assertGreaterEqual(len(r.list()),1)
if __name__=='__main__':unittest.main()
