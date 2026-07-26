import tempfile,unittest
from pathlib import Path
from evoagent.attestation import AttestationRegistry
from evoagent.bundle import BundleRegistry
from evoagent.skill_registry import SkillRegistry,SkillSpec
class BundleTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.src=self.p/'skill.py';self.src.write_text('x=1\n');self.test=self.p/'test.py';self.test.write_text('ok\n');self.cfg=self.p/'cfg.json';self.cfg.write_text('{}');self.a=AttestationRegistry(self.p/'a.json')
  import evoagent.router
  self.a.attest('s@1','evoagent.router:route',tests=[self.test]);self.s=SkillRegistry(self.p/'s.json');self.s.register(SkillSpec('s','1','math','evoagent.router:route',{}, {},('local_compute',),'normal','provisional',{}));self.s.activate('s@1');self.b=BundleRegistry(self.p/'b.json')
 def tearDown(self):self.t.cleanup()
 def make(self):return self.b.create('wf',[self.src],[self.cfg],self.s,self.a)
 def test_bundle_verifies(self):self.assertTrue(self.b.verify(self.make()['bundle_id'],self.s,self.a)['valid'])
 def test_source_change_detected(self):x=self.make();self.src.write_text('x=2');self.assertFalse(self.b.verify(x['bundle_id'],self.s,self.a)['valid'])
 def test_config_change_detected(self):x=self.make();self.cfg.write_text('{\"x\":1}');self.assertFalse(self.b.verify(x['bundle_id'],self.s,self.a)['valid'])
 def test_active_skill_change_detected(self):
  x=self.make()
  self.assertIn('math',self.b.data['bundles'][x['bundle_id']]['manifest']['active_skills'])
 def test_missing_skill_attestation_blocks_creation(self):
  s=SkillRegistry(self.p/'other.json');s.register(SkillSpec('z','1','date','evoagent.router:route',{}, {},(), 'normal','provisional',{}));s.activate('z@1')
  with self.assertRaisesRegex(ValueError,'missing attestation'):self.b.create('bad',[self.src],[self.cfg],s,self.a)
if __name__=='__main__':unittest.main()
