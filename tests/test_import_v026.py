import unittest,tempfile,sys,subprocess,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import import_health as h
class Import026Tests(unittest.TestCase):
 def test_stalled_stage_has_bounded_exit_and_stack(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'x.txt').write_text('fixture')
   code="import sys,time;sys.path.insert(0,sys.argv[1]);import import_health as h;from pathlib import Path\nwith h.session(Path(sys.argv[2]),{'DataRoot':sys.argv[2],'ImportStageTimeoutSeconds':0.25,'ImportHeartbeatSeconds':0.05}):\n with h.file_scope(Path(sys.argv[2])/'x.txt'):\n  with h.phase('EMBEDDING_API'):time.sleep(3)"
   r=subprocess.run([sys.executable,'-c',code,str(Path(h.__file__).parent),tmp],capture_output=True,text=True,timeout=5)
   self.assertEqual(r.returncode,124,r.stderr);state=json.loads((p/'runtime/import-state.json').read_text());self.assertEqual(state['state'],'TIMED_OUT');self.assertEqual(state['stage'],'EMBEDDING_API');self.assertIn('still waiting',r.stderr)
   self.assertTrue(list((p/'runtime/import-traces').rglob('python-stack.log')))
   with h.session(p,{'DataRoot':tmp}):self.assertTrue(h.skip_file(p/'x.txt'))
   (p/'x.txt').write_text('changed input')
   with h.session(p,{'DataRoot':tmp}):self.assertFalse(h.skip_file(p/'x.txt'))
 def test_explicit_retry_does_not_skip(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'x').write_text('x')
   with h.session(p,{'DataRoot':tmp},{'retry_timeouts':True}):self.assertFalse(h.skip_file(p/'x'))
 def test_retry_recovery_skips_only_files_failed_this_invocation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   for name in ['a','b']:(p/name).write_text(name)
   with h.session(p,{'DataRoot':tmp}) as probe:
    for name in ['a','b']:
     info=probe.identify(p/name);probe.exclusions[probe.key(info)]=info
    h.atomic(probe.skip_path,probe.exclusions)
   with h.session(p,{'DataRoot':tmp},{'retry_timeouts':True,'skip_timeout_paths':[str(p/'a')]}):
    self.assertTrue(h.skip_file(p/'a'));self.assertFalse(h.skip_file(p/'b'))
 def test_health_write_failure_stops_instead_of_losing_watchdog(self):
  with tempfile.TemporaryDirectory() as tmp:
   code="import sys,time;sys.path.insert(0,sys.argv[1]);import import_health as h;from pathlib import Path\nwith h.session(Path(sys.argv[2]),{'DataRoot':sys.argv[2],'ImportHeartbeatSeconds':0.05}):\n h.ACTIVE.save=lambda *a:(_ for _ in ()).throw(OSError('fixture'));time.sleep(3)"
   result=subprocess.run([sys.executable,'-c',code,str(Path(h.__file__).parent),tmp],capture_output=True,text=True,timeout=5)
   self.assertEqual(result.returncode,125)
 def test_full_asset_scope_excludes_only_meeting_recordings_and_links(self):
  import worker as w
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'current-state').mkdir();(p/'existing-assets/New Folder').mkdir(parents=True);(p/'existing-assets/Meeting Recordings').mkdir()
   (p/'existing-assets/New Folder/new.srt').write_text('new transcript')
   (p/'existing-assets/inventory.txt').write_text('top level asset')
   (p/'existing-assets/Meeting Recordings/meeting.srt').write_text('excluded')
   found=w.scan({'DataRoot':tmp})
   self.assertTrue(found['complete']);self.assertEqual({f['relative'] for f in found['files']},{'existing-assets/New Folder/new.srt','existing-assets/inventory.txt'})
 def test_successful_work_finishes_cleanly(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   with h.session(p,{'DataRoot':tmp}):
    with h.phase('DATABASE'):pass
   self.assertEqual(json.loads((p/'runtime/import-state.json').read_text())['state'],'COMPLETE')
if __name__=='__main__':unittest.main()
