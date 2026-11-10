import unittest,subprocess,sys,tempfile,json
from pathlib import Path
TOOLS=Path(__file__).resolve().parents[1]/'tools'
class MonitoringIsolationTests(unittest.TestCase):
 def run_case(self,body):
  with tempfile.TemporaryDirectory() as tmp:
   prefix="import sys,time,json,threading;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import import_health as h\nroot=Path(sys.argv[2]);(root/'a.txt').write_text('fixture')\n"
   return subprocess.run([sys.executable,'-c',prefix+body,str(TOOLS),tmp],capture_output=True,text=True,timeout=5)
 def test_denied_status_updates_do_not_abort_successful_work(self):
  result=self.run_case("""real=h.atomic
def denied(path,data):raise PermissionError('controlled status write denial')
h.atomic=denied
with h.session(root,{'DataRoot':str(root),'ImportHeartbeatSeconds':.03}):
 for i in range(8):
  with h.file_scope(root/'a.txt'):
   with h.phase('EMBEDDING_API'):time.sleep(.03)
print('IMPORT_FINISHED')
""")
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('IMPORT_FINISHED',result.stdout);self.assertIn('nonfatal',result.stderr.lower())
 def test_unwritable_status_does_not_disable_real_timeout(self):
  result=self.run_case("""def denied(path,data):raise PermissionError('controlled status write denial')
h.atomic=denied
with h.session(root,{'DataRoot':str(root),'ImportStageTimeoutSeconds':.2,'ImportHeartbeatSeconds':.03}):
 with h.file_scope(root/'a.txt'):
  with h.phase('EMBEDDING_API'):time.sleep(3)
""")
  self.assertEqual(result.returncode,124,result.stderr)
  marker=next(x for x in result.stderr.splitlines() if x.startswith('TD_IMPORT_FAILURE_JSON:'))
  failure=json.loads(marker.split(':',1)[1]);self.assertEqual(failure['stage'],'EMBEDDING_API');self.assertFalse(failure['recoverable']);self.assertEqual(failure['state'],'TIMED_OUT')
 def test_slow_timeout_map_read_does_not_block_initialization(self):
  result=self.run_case("""h.read=lambda path:time.sleep(10)
with h.session(root,{'DataRoot':str(root)}):pass
print('IMPORT_FINISHED')
""")
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('IMPORT_FINISHED',result.stdout)
 def test_slow_status_storage_does_not_block_work_or_watchdog(self):
  result=self.run_case("""def slow(path,data):time.sleep(10)
h.atomic=slow
with h.session(root,{'DataRoot':str(root),'ImportHeartbeatSeconds':.03}):
 with h.phase('EMBEDDING_API'):time.sleep(.1)
print('IMPORT_FINISHED')
""")
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('IMPORT_FINISHED',result.stdout)
if __name__=='__main__':unittest.main()
