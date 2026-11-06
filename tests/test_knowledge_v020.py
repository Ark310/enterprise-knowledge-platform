import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
class CoverageTests(unittest.TestCase):
 def test_visual_claim_must_cite_real_frame(self):
  import knowledge_qa as q
  evidence=[{'evidence_id':'S1','kind':'SOURCE','text':'save the user'}]
  answer={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','basis':'VISUAL','text':'The save button is visible','citations':[{'evidence_id':'S1','excerpt':'save the user'}]}],'limitations':[]}
  self.assertTrue(any('frame' in e.lower() for e in q.validate_answer(answer,evidence)))
 def test_frame_evidence_is_distinct_and_stable(self):
  from knowledge_search import merge_evidence
  rows=[{'kind':'FRAME','frame_id':str(i),'text':'frame'+str(i)} for i in range(2)]
  out=merge_evidence([],rows)
  self.assertEqual(len(out),2)
  self.assertEqual([p['evidence_id'] for p in merge_evidence(out,rows)],['F1','F2'])
 def test_verifier_cannot_pass_incomplete_investigation(self):
  import knowledge_qa as q
  a={'status':'ANSWER','claims':[]}
  v={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'claim_checks':[],'feedback':[],'requested_scope_complete':False,'evidence_coverage_sufficient':False,'coverage_reason':'Ending not read'}
  self.assertTrue(any('coverage' in e.lower() for e in q.validate_verdict(v,a)))
 def test_video_name_normalization_preserves_identity(self):
  from knowledge_visual import recording_key
  self.assertEqual(recording_key('System Admin_ Security_User Master Walkthrough.mp4'),recording_key('System Admin Security User Master Walkthrough'))
  self.assertNotEqual(recording_key('User Master'),recording_key('User Master Advanced'))
 def test_visual_samples_include_ending_and_relevant_topic(self):
  from knowledge_visual import sample_times
  samples=sample_times(780,[{'start_seconds':320,'content_text':'password save outcome'}],['password'])
  self.assertLessEqual(len(samples),12);self.assertIn(320,samples);self.assertTrue(any(x>=775 for x in samples));self.assertTrue(all(0<=x<780 for x in samples))
 def test_no_sample_outside_short_video(self):
  from knowledge_visual import sample_times
  self.assertTrue(all(0<=x<.5 for x in sample_times(.5,[],[])))

class ReviewerRegressions(unittest.TestCase):
 def test_missing_visual_plan_rejected(self):
  import knowledge_qa as q
  n={'conversation_relation':'NEW','request_parts':['Fixture requested task'],'confirmed_context':[],'assumptions':[],'normalized_question':'Did the video save?','needs_clarification':False,'clarification_question':'','changes':[],'search_queries':[]}
  self.assertTrue(q.validate_normalization('Did the video save?',n))
 def test_visual_plan_without_name_requires_clarification(self):
  import knowledge_qa as q
  n={'conversation_relation':'NEW','request_parts':['Fixture requested task'],'confirmed_context':[],'assumptions':[],'normalized_question':'Did the video save?','needs_clarification':False,'clarification_question':'','changes':[],'search_queries':[],'visual_check':True,'recording_names':[]}
  self.assertTrue(q.validate_normalization('Did the video save?',n))
 def test_exact_relative_path_resolves_duplicate_basename(self):
  from knowledge_visual import recording_matches
  videos=[{'storage_uri':'file:///C:/Data/current-state/Review%20Sample.mp4'},{'storage_uri':'file:///C:/Data/existing-assets/Review%20Sample.mp4'}]
  self.assertEqual(recording_matches(videos,'current-state/Review Sample.mp4',Path('C:/Data')),[videos[0]])
  self.assertEqual(len(recording_matches(videos,'Review Sample',Path('C:/Data'))),2)

class FrameBatchIntegrity(unittest.TestCase):
 def test_batch_checks_recording_again_after_frame_preparation(self):
  import knowledge_visual as kv,worker as w
  import tempfile
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);rec=root/'Demo.mp4';rec.write_bytes(b'initial');digest=w.file_hash(rec)
   class Query:
    def fetchall(self):return [{'id':'version','storage_uri':rec.as_uri(),'content_sha256':digest}]
   def changed(*args,**kwargs):rec.write_bytes(b'changed');return []
   with patch.object(w,'q',return_value=Query()),patch('module_review.duration',return_value=(4,'ffmpeg')),patch('video_evidence.frames',side_effect=changed):
    frames,report=kv.prepare(None,{'DataRoot':str(root)},{'visual_check':True,'recording_names':['Demo'],'keywords':[]},[])
   self.assertFalse(frames)
   self.assertEqual(report['recordings'][0]['status'],'UNAVAILABLE')

if __name__=='__main__':unittest.main()
