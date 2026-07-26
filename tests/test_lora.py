import json,tempfile,unittest
from pathlib import Path
from evoagent.lora import LoraSpec,build_adapter,verify_adapter
class LoraTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
  self.base=self.p/'base.bin';self.base.write_text('base-weights')
  self.manifest=self.p/'data.json';self.manifest.write_text(json.dumps({'examples':1234}))
 def tearDown(self):self.t.cleanup()
 def spec(self):return LoraSpec(base_model='qwen2-7b',adapter_name='math-lora',rank=16,alpha=32,target_modules=('q_proj','k_proj','v_proj','o_proj'),quantization='qlora-4bit',target_task='math',version='1')
 def test_build_and_verify_round_trip(self):
  spec=self.spec();attest=build_adapter(spec,self.manifest,self.base,Path(self.t.name)/'out',train_steps=20,train_tokens=4000);self.assertTrue(attest['lora_json_sha256']);self.assertTrue(verify_adapter(Path(self.t.name)/'out'/f'{spec.adapter_name}_v1.attestation.json',spec,self.base,self.manifest)['valid'])
 def test_tampered_weights_rejected(self):
  spec=self.spec();attest=build_adapter(spec,self.manifest,self.base,Path(self.t.name)/'out',train_steps=10,train_tokens=1000);weights=Path(self.t.name)/'out'/f'{spec.adapter_name}_v1.safetensors.json';weights.write_text('tampered');v=verify_adapter(Path(self.t.name)/'out'/f'{spec.adapter_name}_v1.attestation.json',spec,self.base,self.manifest);self.assertFalse(v['valid']);self.assertIn('mismatch:weights_sha256',v['reasons'])
 def test_invalid_rank_rejected(self):
  with self.assertRaises(ValueError):LoraSpec(base_model='',adapter_name='x')
if __name__=='__main__':unittest.main()
