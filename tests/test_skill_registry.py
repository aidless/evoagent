import tempfile,unittest
from pathlib import Path
from evoagent.skill_registry import SkillRegistry,SkillSpec,validate_contract
from evoagent.attestation import AttestationRegistry
S=lambda v='1',level='provisional',perm=():SkillSpec('calc',v,'math','evo.calc',{'required':['text'],'properties':{'text':{'type':'string'}}},{'required':['answer'],'properties':{'answer':{'type':'number'}}},perm,'normal',level,{})
class SkillRegistryTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=SkillRegistry(Path(self.t.name)/'skills.json')
 def tearDown(self):self.t.cleanup()
 def test_register_activate_resolve(self):self.r.register(S());self.r.activate('calc@1');self.assertEqual(self.r.resolve('math')['entrypoint'],'evo.calc')
 def test_duplicate_version_rejected(self):
  self.r.register(S())
  with self.assertRaises(ValueError):self.r.register(S())
 def test_experimental_not_active(self):
  self.r.register(S(level='experimental'))
  with self.assertRaises(ValueError):self.r.activate('calc@1')
 def test_permission_denied(self):
  with self.assertRaisesRegex(ValueError,'permission denied'):self.r.register(S(perm=('delete_files',)))
 def test_activation_replaces_same_task_atomically(self):self.r.register(S('1'));self.r.register(S('2'));self.r.activate('calc@1');old=self.r.activate('calc@2');self.assertEqual(old,'calc@1');self.assertEqual(self.r.resolve('math')['version'],'2')
 def test_contract(self):self.assertTrue(validate_contract({'text':'2+2'},S().input_schema))
 def test_contract_missing(self):
  with self.assertRaisesRegex(ValueError,'missing'):validate_contract({},S().input_schema)
 def test_contract_type(self):
  with self.assertRaisesRegex(ValueError,'wrong type'):validate_contract({'text':3},S().input_schema)
 def test_strict_attestation_blocks_missing(self):
  reg=SkillRegistry(self.r.path,attestations=AttestationRegistry(self.r.path.parent/'a.json'),strict_attestation=True);reg.register(S('9'))
  with self.assertRaisesRegex(ValueError,'attestation'):reg.activate('calc@9')
if __name__=='__main__':unittest.main()
