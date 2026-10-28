import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
try: import worker as w
except ImportError: w=None
class EvidenceTests(unittest.TestCase):
 def test_worker_exists(self): self.assertIsNotNone(w,'Evidence worker not implemented')
 def test_srt_preserves_original_timestamps(self):
  self.assertIsNotNone(w)
  c=w.srt_units('1\n00:08:15,100 --> 00:08:18,200\nTwo Factor Authentication\n\n2\n00:08:19,000 --> 00:08:20,000\nTOTP\n')
  self.assertEqual(len(c),2);self.assertAlmostEqual(c[0]['start'],495.1);self.assertEqual(c[0]['text'],'Two Factor Authentication')
 def test_chunk_bounds_no_text_loss(self):
  self.assertIsNotNone(w);s='word '*2500;c=w.chunks(s,500)
  self.assertTrue(all(len(x)<=500 for x in c));self.assertEqual(''.join(c),s)
 def test_scan_excludes_meetings_and_symlinks(self):
  self.assertIsNotNone(w)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'current-state').mkdir();(root/'existing-assets'/'Meeting Recordings').mkdir(parents=True)
   (root/'current-state'/'test.srt').write_text('ok');(root/'existing-assets'/'Meeting Recordings'/'secret.txt').write_text('exclude')
   for x in ['Confluence Articles','REST API','Sharepoint','VLCs']:(root/'existing-assets'/x).mkdir()
   try:(root/'current-state'/'escape').symlink_to(root/'existing-assets'/'Meeting Recordings',target_is_directory=True)
   except OSError:pass
   cfg={'DataRoot':str(root)};r=w.scan(cfg)
   self.assertEqual([x['relative'] for x in r['files']],['current-state/test.srt']);self.assertTrue(r['complete'])
 def test_missing_root_is_not_successful_full_scan(self):
  self.assertIsNotNone(w)
  with tempfile.TemporaryDirectory() as d:self.assertFalse(w.scan({'DataRoot':d})['complete'])
 def test_bad_srt_range_rejected(self):
  self.assertIsNotNone(w)
  with self.assertRaises(ValueError):w.srt_units('1\n00:00:05,000 --> 00:00:01,000\nbad\n')
 def test_no_binary_as_text(self):
  self.assertIsNotNone(w)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.snag';p.write_bytes(b'\xcbTSC SNAGN')
   self.assertEqual(w.extract(p)['status'],'BLOCKED')
class ContractTests(unittest.TestCase):
 def test_original_test_requests_valid(self):
  for p in (Path(__file__).resolve().parents[1]/'tests/scenarios').glob('*-original.json'):
   self.assertEqual(w.validate_contract(json.loads(p.read_text()),'START_CURRENT_STATE'),[],str(p))
 def test_extra_contract_field_rejected(self):
  p=Path(__file__).resolve().parents[1]/'tests/scenarios/T02-original.json';obj=json.loads(p.read_text());obj['invented']='bad'
  self.assertTrue(w.validate_contract(obj))
 def test_no_frames_rejects_visual_claim(self):
  manifest={'transcript_file':'x.srt','transcript':[],'frames':[],'request':{'payload':{'recording_member':'x.mp4'}}}
  obj={'payload':{'observations':[{'level':'OBSERVED_VISUAL','citations':[{'source_type':'RECORDING_VISUAL','file':'x.mp4','locator':'00:01','excerpt_or_observation':'checkbox'}]}]}}
  self.assertTrue(w.citation_errors(obj,manifest,[]))
 def test_fabricated_excerpt_rejected(self):
  manifest={'transcript_file':'x.srt','transcript':[{'content_text':'actual words'}],'frames':[],'request':{'payload':{'recording_member':'x.mp4'}}}
  obj={'citation':{'source_type':'RECORDING_AUDIO_TRANSCRIPT','file':'x.srt','locator':'cue 1','excerpt_or_observation':'invented'}}
  self.assertTrue(w.citation_errors(obj,manifest,[]))
 def test_bad_query_profile_endpoint_rejected(self):
  with self.assertRaises(ValueError):w.ollama({'OllamaUrl':'https://example.com'},'/api/tags')

class RegressionTests(unittest.TestCase):
 def test_malformed_payload_returns_errors_instead_of_crashing(self):
  self.assertTrue(w.validate_contract({'payload':[]},'CURRENT_STATE_HANDOFF'))
 def test_non_object_output_returns_errors(self):
  self.assertTrue(w.validate_contract(['not','a','contract']))
 def test_visual_level_cannot_use_only_transcript(self):
  manifest={'transcript_file':'x.srt','transcript':[{'content_text':'actual','locator':{'cue':1}}],'frames':[{'seconds':1}],'request':{'payload':{'recording_member':'x.mp4'}}}
  obj={'payload':{'observations':[{'level':'OBSERVED_VISUAL','citations':[{'source_type':'RECORDING_AUDIO_TRANSCRIPT','file':'x.srt','locator':'{"cue":1}','excerpt_or_observation':'actual'}]}]}}
  self.assertTrue(w.citation_errors(obj,manifest,[]))
 def test_unsupplied_frame_timestamp_rejected(self):
  manifest={'transcript_file':'x.srt','transcript':[],'frames':[{'seconds':1}],'request':{'payload':{'recording_member':'x.mp4'}}}
  obj={'citation':{'source_type':'RECORDING_VISUAL','file':'x.mp4','locator':'frame_seconds=999','excerpt_or_observation':'visible checkbox'}}
  self.assertTrue(w.citation_errors(obj,manifest,[]))
 def test_exact_text_locator_and_excerpt_accepted(self):
  manifest={'transcript_file':'x.srt','transcript':[{'content_text':'actual words','locator':{'cue':1}}],'frames':[],'request':{'payload':{'recording_member':'x.mp4'}}}
  obj={'citation':{'source_type':'RECORDING_AUDIO_TRANSCRIPT','file':'x.srt','locator':'{"cue":1}','excerpt_or_observation':'actual'}}
  self.assertEqual(w.citation_errors(obj,manifest,[]),[])
 def test_current_state_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'current-state').mkdir();(root/'existing-assets').mkdir();p=root/'existing-assets/x.mp4';p.write_bytes(b'video')
   with self.assertRaises(ValueError):w.safe_path(root/'current-state',(root/'current-state/../existing-assets/x.mp4').resolve())

if __name__=='__main__':unittest.main()
