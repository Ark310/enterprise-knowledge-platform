import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import knowledge_qa as qa,knowledge_visual as kv
class Video025Tests(unittest.TestCase):
 def norm(self,q,**kw):
  return dict(normalized_question=q,needs_clarification=False,clarification_question='',changes=[],search_queries=[q],visual_check=True,recording_names=[],conversation_relation='NEW',request_parts=[q],confirmed_context=[],assumptions=[],**kw)
 def test_three_captured_live_failures(self):
  cases=json.loads((Path(__file__).parent/'fixtures/v025/normalization-regressions.json').read_text())
  self.assertEqual(len(cases),3)
  for c in cases:
   with self.subTest(question=c['question']):self.assertEqual(qa.validate_normalization(c['question'],qa.canonical_normalization(c['question'],c['normalization'])),[])
 def test_article_screenshot_is_not_unnamed_video(self):
  q='I need to add a new employee to TradeDesk. Show screenshots from the articles.'
  n=qa.canonical_normalization(q,self.norm(q));self.assertFalse(n['visual_check']);self.assertIn('ARTICLE_IMAGE',n['visual_targets']);self.assertEqual(qa.validate_normalization(q,n),[])
 def test_uploaded_image_is_not_unnamed_video(self):
  q='Explain this screenshot';n=qa.canonical_normalization(q,self.norm(q,visual_targets=['USER_IMAGE']));self.assertFalse(n['visual_check']);self.assertEqual(qa.validate_normalization(q,n),[])
 def test_named_video_defaults_to_frames(self):
  q='What does Sections 3 and 4 explain?';n=self.norm(q);n.update(recording_names=['Sections 3 and 4'],visual_check=False)
  n=qa.canonical_normalization(q,n);self.assertTrue(n['visual_check']);self.assertEqual(qa.validate_normalization(q,n),[])
 def test_transcript_only_does_not_request_frames(self):
  q='Using the transcript only, summarize Sections 3 and 4';n=self.norm(q);n['recording_names']=['Sections 3 and 4'];self.assertFalse(qa.canonical_normalization(q,n)['visual_check'])
 def test_unnamed_video_still_requires_selection(self):
  q='Show the video frames';n=qa.canonical_normalization(q,self.norm(q));self.assertTrue(qa.validate_normalization(q,n))
 def test_pins_are_preserved(self):
  q='How do I draw down a forward?';pin='existing-assets/VLCs/TradeDesk/Sections 3 and 4 [iuinh8jZ7J8].mp4'
  n=qa.canonical_normalization(q,self.norm(q),[pin]);self.assertEqual(n['recording_names'],[pin]);self.assertTrue(n['visual_check'])
 def test_human_title_resolves_youtube_suffix(self):
  rows=[{'storage_uri':'file:///data/Sections%203%20and%204%20%5Biuinh8jZ7J8%5D.mp4'}];self.assertEqual(kv.recording_matches(rows,'Sections 3 and 4','/data'),rows)
 def test_duplicate_human_title_is_not_arbitrarily_resolved(self):
  rows=[{'storage_uri':f'file:///data/{d}/Sections%203%20and%204%20%5Biuinh8jZ7J8%5D.mp4'} for d in ['a','b']];self.assertEqual(len(kv.recording_matches(rows,'Sections 3 and 4','/data')),2)
 def test_point_subtitle_preserves_original_time_and_text(self):
  import worker as w
  from transcript_groups import group_cues
  text='1\n00:00:02,000 --> 00:00:02,000\nA point cue\n\n2\n00:00:02,000 --> 00:00:05,000\nContinued speech.\n'
  cues=w.srt_units(text,allow_points=True)
  self.assertEqual((cues[0]['start'],cues[0]['end']),(2,2));self.assertEqual(cues[0]['locator']['timing_quality'],'POINT_ONLY')
  grouped=group_cues(cues);self.assertIn('A point cue',grouped[0]['text']);self.assertEqual((grouped[0]['start'],grouped[0]['end']),(2,5))
 def test_reversed_subtitle_still_fails(self):
  import worker as w
  with self.assertRaises(ValueError):w.srt_units('1\n00:00:05,000 --> 00:00:02,000\nBad',allow_points=True)
 def test_topic_samples_take_priority_over_boundaries(self):
  passages=[{'start_seconds':500,'content_text':'forward drawdown'}];times=kv.sample_times(1500,passages,['drawdown'],cap=4);self.assertIn(500,times)
if __name__=='__main__':unittest.main()
