import tempfile,unittest
from pathlib import Path
from evoagent.lora_backends import LoraBackendSpec,LoraBackendRegistry,build_default_backends
class LoraBackendTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
 def tearDown(self):self.t.cleanup()
 def test_runtime_check_reports_missing(self):
  spec=LoraBackendSpec(id='b1',family='x',quantization='qlora-4bit');rc=spec.runtime_check();self.assertIn('missing_modules',rc);self.assertIsInstance(rc['missing_modules'],list)
 def test_register_and_audit(self):
  reg=LoraBackendRegistry(self.p/'b.json')
  spec=LoraBackendSpec(id='b1',family='x',quantization='qlora-4bit')
  rc=reg.register(spec);self.assertIn('id',rc);self.assertEqual(reg.audit()['backends']['b1']['family'],'x')
 def test_duplicate_register_rejected(self):
  reg=LoraBackendRegistry(self.p/'b.json');spec=LoraBackendSpec(id='b1',family='x',quantization='qlora-4bit')
  reg.register(spec)
  with self.assertRaises(ValueError):reg.register(spec)
 def test_build_default_backends_creates_qwen(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'b.json';reg=build_default_backends(p);self.assertIn('peft-qlora-4bit-qwen',reg.audit()['backends'])
if __name__=='__main__':unittest.main()
