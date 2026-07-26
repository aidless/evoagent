import tempfile,unittest
from pathlib import Path
from evoagent.protocol import Outcome
from evoagent.shadow import ShadowRecorder,enforce_shadow_safety,production_evidence,redact
from evoagent.version_registry import VersionRegistry
class ShadowTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.s=ShadowRecorder(self.p/'shadow.jsonl','base','cand')
 def tearDown(self):self.t.cleanup()
 def o(self,i,p,safety=0,cost=1):return Outcome(str(i),p,1 if p else 0,cost,1,safety,{'core':1})
 def test_redaction(self):
  x=redact('mail a@b.com phone +86 138 0013 8000 api_key=secret');self.assertNotIn('a@b.com',x);self.assertNotIn('secret',x);self.assertIn('<EMAIL>',x)
 def test_pair_record_hashes_raw_input(self):
  r=self.s.record('1','private a@b.com',self.o(1,False),self.o(1,True));self.assertNotIn('a@b.com',r['input_redacted']);self.assertEqual(len(r['input_sha256']),64)
 def test_clear_shadow_improvement_passes(self):
  for i in range(100):self.s.record(str(i),'x',self.o(i,i>=30),self.o(i,True))
  r=self.s.summarize({'min_gain':.1,'bootstrap_iterations':1000});self.assertTrue(r['shadow_passed'],r)
 def test_safety_auto_downgrades(self):
  reg=VersionRegistry(self.p/'reg.json');reg.register('cand','agent');reg.transition('cand','provisional',{'development_passed':True,'rollback_available':True})
  for i in range(20):self.s.record(str(i),'x',self.o(i,True),self.o(i,True,safety=1 if i==0 else 0))
  summary=self.s.summarize({'bootstrap_iterations':200});e=enforce_shadow_safety(summary,reg,'cand');self.assertIsNotNone(e);self.assertEqual(reg.get('cand')['level'],'experimental')
 def test_production_evidence_needs_human(self):
  x=production_evidence({'shadow_passed':True,'n':100,'decision':{'safety_violations':0}},False);self.assertFalse(x['human_approved'])
if __name__=='__main__':unittest.main()
