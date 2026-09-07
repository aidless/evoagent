import unittest,subprocess,sys,os,json,tempfile
from pathlib import Path
class VersionAuditCLITests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.p=Path(self.t.name)
        self.registry_path=Path(self.t.name)/'r.json'
        self.registry_path.write_text(json.dumps({'versions':{'v@1':{'level':'provisional'}},'history':[{'action':'register','version_id':'v@1'},{'action':'transition','version_id':'v@1','from':'experimental','to':'provisional'}]}))
    def tearDown(self):
        self.t.cleanup()
    def invoke_cli(self,*args):
        env=os.environ.copy()
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        proc=subprocess.run([sys.executable,'-m','evoagent.version_audit',*args,'--registry',str(self.registry_path)],env=env,capture_output=True,text=True,check=True)
        return json.loads(proc.stdout)
    def _init_registry(self):
        # setUp already creates a fresh registry for each test.
        return None
    def test_list(self):
        self._init_registry();self.assertIn('v@1',self.invoke_cli('list')['versions'])
    def test_audit_returns_events(self):
        r=self.invoke_cli('audit')
        self.assertEqual(len(r['events']),2)
    def test_audit_filter_by_version(self):
        r=self.invoke_cli('audit','--version','v@1')
        self.assertGreaterEqual(len(r['events']),2)
    def test_audit_filter_by_action(self):
        r=self.invoke_cli('audit','--action','transition')
        self.assertEqual(len(r['events']),1)
    def test_audit_filter_combined(self):
        r=self.invoke_cli('audit','--version','v@1','--action','transition','--limit','5')
        self.assertEqual(r['events'][0]['to'],'provisional')
if __name__=='__main__':
    unittest.main()
