import unittest,sys,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import module_review as m
class FrameCompatibilityTests(unittest.TestCase):
 def test_modern_build_does_not_receive_removed_vsync(self):
  self.assertEqual(m.frame_sync_args(' -fps_mode    set fps mode\n -vsync   deprecated'),['-fps_mode','vfr'])
 def test_legacy_build_uses_numeric_vsync(self):self.assertEqual(m.frame_sync_args(' -vsync    video sync method'),['-vsync','2'])
 def test_no_supported_mode_is_explicit_failure(self):
  with self.assertRaises(ValueError):m.frame_sync_args('other options only')
 def test_actual_error_is_retained_and_shown(self):
  with tempfile.TemporaryDirectory() as td:
   def run(args,**kw):
    if '-version' in args:return subprocess.CompletedProcess(args,0,'fixture version','')
    if '-h' in args:return subprocess.CompletedProcess(args,0,' -fps_mode    mode','')
    self.assertNotIn('-vsync',args)
    return subprocess.CompletedProcess(args,1,'',"Unrecognized option 'fixture-only'.")
   with patch.object(m.subprocess,'run',run):
    with self.assertRaisesRegex(ValueError,'Unrecognized option'):
     m.decode_frames('ffmpeg','video.mp4',Path(td),dict(start=0,end=120),Path(td)/'frame-%04d.jpg')
   self.assertIn('fixture-only',(Path(td)/'ffmpeg-stderr.txt').read_text())
if __name__=='__main__':unittest.main()
