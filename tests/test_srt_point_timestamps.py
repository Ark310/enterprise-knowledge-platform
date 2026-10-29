"""Regression tests for point-only SRT cues; no source transcript content is included."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w
class PointCueTests(unittest.TestCase):
 def test_zero_duration_retains_text_and_exact_times(self):
  units=w.srt_units('134\n00:08:19,370 --> 00:08:19,370\nExample narration.\n')
  self.assertEqual(len(units),1);self.assertEqual(units[0]['text'],'Example narration.')
  self.assertEqual(units[0]['start'],499.37);self.assertEqual(units[0]['end'],499.37)
  self.assertEqual(units[0]['locator']['timing_status'],'POINT_ONLY')
 def test_zero_duration_marks_file_partial_with_warning(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'example.srt';p.write_text('1\n00:00:01,000 --> 00:00:01,000\nA point cue.\n')
   data=w.extract(p);self.assertEqual(data['status'],'PARTIAL');self.assertTrue(data['warnings']);self.assertEqual(len(data['units']),1)
 def test_reverse_duration_still_rejected(self):
  with self.assertRaises(ValueError):w.srt_units('1\n00:00:05,000 --> 00:00:01,000\nBad ordering.\n')
 def test_normal_cue_unchanged(self):
  row=w.srt_units('7\n00:00:05,000 --> 00:00:06,000\nNormal.\n')[0]
  self.assertEqual(row['start'],5);self.assertEqual(row['end'],6);self.assertNotIn('timing_status',row['locator'])
if __name__=='__main__':unittest.main()
