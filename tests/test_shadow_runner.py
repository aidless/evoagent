import json,sys,tempfile,unittest
from pathlib import Path
from evoagent.shadow import ShadowRecorder
from evoagent.shadow_runner import CommandSpec,execute,run_shadow_task
class ShadowRunnerTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=ShadowRecorder(Path(self.t.name)/'s.jsonl','base','cand')
 def tearDown(self):self.t.cleanup()
 def spec(self,code,timeout=5):return CommandSpec((sys.executable,'-c',code),timeout)
 def test_returns_only_baseline_output(self):
  b=self.spec("import json;print(json.dumps({'passed':True,'output':'stable'}))");c=self.spec("import json;print(json.dumps({'passed':True,'output':'secret-candidate'}))");r=run_shadow_task(self.r,'1','hello',b,c);self.assertEqual(r['user_output'],'stable');self.assertNotIn('secret-candidate',json.dumps(r,default=str));self.assertFalse(r['candidate_output_exposed'])
 def test_timeout_is_failure(self):
  _,o=execute(self.spec('import time;time.sleep(2)',.05),'1','x',True);self.assertFalse(o.passed);self.assertEqual(o.details['error'],'timeout')
 def test_invalid_json_is_failure(self):
  _,o=execute(self.spec("print('not-json')"),'1','x',True);self.assertFalse(o.passed);self.assertIn('invalid_output',o.details['error'])
 def test_side_effect_report_becomes_safety_violation(self):
  _,o=execute(self.spec("import json;print(json.dumps({'passed':True,'side_effects':1}))"),'1','x',True);self.assertEqual(o.safety_violations,1)
 def test_shadow_environment_flag(self):
  code="import json,os;print(json.dumps({'passed':os.environ['SHADOW_MODE']=='1'}))";_,o=execute(self.spec(code),'1','private',True);self.assertTrue(o.passed)
if __name__=='__main__':unittest.main()
