import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w
class TranscriptGroupingTests(unittest.TestCase):
 def test_groups_cues_without_text_loss(self):
  from transcript_groups import group_cues
  cues=w.srt_units('1\n00:00:00,000 --> 00:00:10,000\nOpen User Master.\n\n2\n00:00:10,000 --> 00:00:20,000\nChoose the user.\n\n3\n00:00:20,000 --> 00:00:35,000\nSave your change.')
  rows=group_cues(cues)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],'\n'.join(c['text'] for c in cues))
  self.assertEqual(rows[0]['locator']['cue_ids'],[1,2,3]);self.assertEqual(rows[0]['end'],35)
 def test_pause_and_maximum_boundaries(self):
  from transcript_groups import group_cues
  cues=[{'text':'Step.','start':a,'end':b,'locator':{'cue':i}} for i,(a,b) in enumerate([(0,20),(20,40),(60,80),(80,100),(100,120)],1)]
  rows=group_cues(cues);self.assertEqual([r['locator']['cue_ids'] for r in rows],[[1,2],[3,4],[5]])
 def test_long_cue_keeps_exact_offsets_without_inventing_time(self):
  from transcript_groups import group_cues
  text='word '*1000;c=[{'text':text,'start':0,'end':90,'locator':{'cue':1}}]
  rows=group_cues(c);self.assertEqual(''.join(r['text'] for r in rows),text)
  self.assertTrue(all(len(r['text'])<=1800 for r in rows));self.assertTrue(all(r['start']==0 and r['end']==90 for r in rows))
 def test_bad_times_rejected(self):
  from transcript_groups import group_cues
  with self.assertRaises(ValueError):group_cues([{'text':'x','start':3,'end':2,'locator':{'cue':1}}])
class ComparisonTests(unittest.TestCase):
 def test_recall_and_rank_overlap_are_not_interchangeable(self):
  from retrieval_v017 import overlap
  self.assertEqual(overlap(['a','b','c'],['a','c']),{'shared':2,'reference_count':3,'candidate_count':2,'recall':2/3})
 def test_modes_reject_unknown_value(self):
  from retrieval_v017 import validate_mode
  with self.assertRaises(ValueError):validate_mode('magic')
 def test_index_dimension_identifier_guard(self):
  from retrieval_v017 import index_spec
  self.assertEqual(index_spec('11111111-1111-1111-1111-111111111111',2560)['dimensions'],2560)
  with self.assertRaises(ValueError):index_spec('bad',2560)
  with self.assertRaises(ValueError):index_spec('11111111-1111-1111-1111-111111111111',5000)
if __name__=='__main__':unittest.main()

class FrameCacheTests(unittest.TestCase):
 def test_missing_or_changed_cached_frame_is_not_reused(self):
  from video_evidence import valid_cache
  import tempfile,json
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'frame.jpg';p.write_bytes(b'first')
   rows=[{'path':str(p),'sha256':w.file_hash(p),'seconds':1}]
   self.assertTrue(valid_cache(rows));p.write_bytes(b'changed');self.assertFalse(valid_cache(rows));p.unlink();self.assertFalse(valid_cache(rows))
 def test_cache_key_changes_with_source_or_sampling(self):
  from video_evidence import cache_key
  self.assertNotEqual(cache_key('a','b',0,120,60),cache_key('c','b',0,120,60))
  self.assertNotEqual(cache_key('a','b',0,120,60),cache_key('a','b',0,120,80))

class AdditionalCacheTests(unittest.TestCase):
 def test_structurally_corrupt_cache_rebuilds(self):
  from video_evidence import valid_cache
  for rows in ({},[None],[{}],[{'path':'missing'}]):self.assertFalse(valid_cache(rows))

class DurationTests(unittest.TestCase):
 def test_transcript_past_recording_duration_is_rejected(self):
  from transcript_groups import group_cues
  with self.assertRaises(ValueError):group_cues([{'text':'too late','start':0,'end':9,'locator':{'cue':1}}],duration_seconds=3)

class FrameTimestampTests(unittest.TestCase):
 def test_decoder_lookahead_does_not_invent_an_extra_output_frame(self):
  from video_evidence import decoded_times
  stderr='Parsed_showinfo pts_time:0\nParsed_showinfo pts_time:2\nParsed_showinfo pts_time:4'
  self.assertEqual(decoded_times(stderr,2),[0,2])
  with self.assertRaises(ValueError):decoded_times(stderr,4)
