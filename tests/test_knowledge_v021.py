import sys,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
class ScopeTests(unittest.TestCase):
 def test_exact_release_is_not_lost_beneath_four_newer_broad_matches(self):
  from knowledge_scope import choose_releases
  docs=[{'version_id':str(i),'storage_uri':f'file:///a/tradedesk/release_notes/Version 3.0.{i}.0/article.md','usable_units':1,'matching_units':1,'term_counts':{'North Bank':0,'North':1}} for i in range(8)]
  exact={'version_id':'exact','storage_uri':'file:///a/tradedesk/release_notes/Version 2.1.0.0/article.md','usable_units':1,'matching_units':1,'term_counts':{'North Bank':1,'North':1}};docs.append(exact)
  ids,req=choose_releases(docs,['North Bank','North'],'tradedesk')
  self.assertIn('exact',ids);self.assertTrue(any(x['term']=='North Bank' and x['version_id']=='exact' for x in req))
 def test_unrelated_product_cannot_take_release_read_slots(self):
  from knowledge_scope import choose_releases
  docs=[{'version_id':'web','storage_uri':'file:///a/web4/release_notes/Version 9.0.0.0/article.md','usable_units':1,'matching_units':1,'term_counts':{'North':1}}, {'version_id':'fx','storage_uri':'file:///a/tradedesk/release_notes/Version 3.0.0.0/article.md','usable_units':1,'matching_units':1,'term_counts':{'North':1}}]
  ids,_=choose_releases(docs,['North'],'tradedesk');self.assertIn('fx',ids);self.assertNotIn('web',ids)
 def test_companion_is_same_directory_and_same_stem(self):
  from knowledge_scope import companion
  video='file:///C:/Data/current-state/System%20Admin_%20User.mp4'
  self.assertTrue(companion(video,'file:///C:/Data/current-state/System%20Admin_%20User_Transcript.docx'))
  self.assertTrue(companion(video,'file:///C:/Data/current-state/System%20Admin_%20User.srt'))
  self.assertFalse(companion(video,'file:///C:/Data/existing-assets/System%20Admin_%20User.srt'))
  self.assertFalse(companion(video,'file:///C:/Data/current-state/System%20Admin_%20User%20Advanced.srt'))
 def test_mandatory_passage_survives_optional_crowding(self):
  from knowledge_scope import assemble
  required=[{'kind':'SOURCE','unit_id':'important','text':'correct transcript'}]
  optional=[{'kind':'SOURCE','unit_id':str(i),'text':'irrelevant'*1000} for i in range(20)]
  evidence=assemble([],required,optional,char_budget=60)
  self.assertEqual(evidence[0]['unit_id'],'important')
 def test_host_rejects_pass_with_missing_requested_scope(self):
  import knowledge_qa as q
  a={'status':'ANSWER','claims':[]};v={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'evidence_coverage_sufficient':True,'coverage_reason':'narrow answer','requested_scope_complete':True,'claim_checks':[],'feedback':[]}
  self.assertTrue(q.validate_verdict(v,a,{'scope':{'blocking_errors':['Matching transcript not supplied']}}))
 def test_asked_scope_is_separate_from_supported_claims(self):
  import knowledge_qa as q
  a={'status':'ANSWER','claims':[]};v={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'evidence_coverage_sufficient':True,'coverage_reason':'narrow answer','requested_scope_complete':False,'claim_checks':[],'feedback':[]}
  self.assertTrue(q.validate_verdict(v,a))
class EvidenceBudgetTests(unittest.TestCase):
 def test_required_sources_share_small_budget(self):
  from knowledge_scope import assemble
  required=[{'kind':'SOURCE','unit_id':str(i),'version_id':'first','text':'x'*30} for i in range(5)]+[{'kind':'SOURCE','unit_id':'last','version_id':'second','text':'y'*30}]
  ev=assemble([],required,[],char_budget=90)
  self.assertIn('last',[p['unit_id'] for p in ev])

class ReviewRegressions(unittest.TestCase):
 def test_sampled_flag_without_supplied_frame_blocks_scope(self):
  from knowledge_scope import completeness
  b={'blocking_errors':[],'required_version_ids':[],'recordings':[]}
  visual={'requested':True,'recordings':[{'requested_name':'Demo','source_version_id':'v','status':'SAMPLED'}]}
  self.assertTrue(completeness(b,[],[],visual)['blocking_errors'])
 def test_empty_visual_recording_list_blocks_scope(self):
  from knowledge_scope import completeness
  b={'blocking_errors':[],'required_version_ids':[],'recordings':[]}
  self.assertTrue(completeness(b,[],[],{'requested':True,'recordings':[]})['blocking_errors'])
 def test_followup_new_required_displaces_old_optional_without_id_reuse(self):
  from knowledge_scope import assemble
  old=[{'evidence_id':'S'+str(i+1),'kind':'SOURCE','unit_id':str(i),'version_id':'old','text':'optional'} for i in range(80)]
  required=[{'kind':'SOURCE','unit_id':'new','version_id':'required','text':'essential'}]
  out=assemble(old,required,[],max_items=80)
  self.assertEqual(out[0]['unit_id'],'new');self.assertEqual(out[0]['evidence_id'],'S81')
  self.assertTrue(all(p['evidence_id']=='S'+str(int(p['unit_id'])+1) for p in out[1:]))
 def test_explicit_other_product_families_are_scoped(self):
  from knowledge_scope import requested_family
  for name,expected in [('FormFlow','formflow'),('SalesHub','saleshub'),('REST API','api')]:
   self.assertEqual(requested_family({'conversation_relation':'NEW','request_parts':['Fixture requested task'],'confirmed_context':[],'assumptions':[],'normalized_question':f'Latest {name} release changes?'}),expected)

class FollowupSafetyTests(unittest.TestCase):
 def test_frame_ids_do_not_reuse_dropped_audit_ids(self):
  from knowledge_search import merge_evidence
  out=merge_evidence([],[{'kind':'FRAME','frame_id':'new','text':'frame'}],reserved_ids=['F80'])
  self.assertEqual(out[0]['evidence_id'],'F81')
 def test_invalid_verdict_does_not_unlock_followup_arguments(self):
  import knowledge_qa as q
  malformed={'retrieval_queries':'not an array'}
  self.assertFalse(q.may_investigate(malformed,{'scope':{'blocking_errors':['missing transcript']}}))

if __name__=='__main__':unittest.main()
