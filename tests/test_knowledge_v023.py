import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import knowledge_qa as qa
class PartialTests(unittest.TestCase):
 def setUp(self):
  self.ev=[{'kind':'SOURCE','evidence_id':'S1','file':'guide.md','text':'Enable two factor authentication and Save.'}]
  self.a={'status':'PARTIAL','clarification_question':'Is the provider already configured?','claims':[{'id':'C1','text':'Enable two factor authentication and Save.','basis':'SOURCE','citations':[{'evidence_id':'S1','excerpt':self.ev[0]['text']}]}],'limitations':[],'unresolved':['Provider integration settings are not established.'],'procedure_complete':False}
  self.v={'decision':'PARTIAL_PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'requested_scope_complete':False,'evidence_coverage_sufficient':True,'coverage_reason':'Useful cited user steps, missing integration explicitly bounded.','claim_checks':[{'claim_id':'C1','supported':True,'reason':'Literal source support'}],'feedback':[]}
 def test_partial_with_useful_supported_steps_can_be_approved(self):
  self.assertEqual(qa.validate_answer(self.a,self.ev),[]);self.assertEqual(qa.validate_verdict(self.v,self.a,{}),[])
 def test_partial_cannot_publish_unknown_or_fabricated_citations(self):
  self.a['claims'][0]['citations'][0]['excerpt']='Enter secret keys';self.assertTrue(qa.validate_answer(self.a,self.ev))
 def test_partial_requires_explicit_unresolved_items(self):
  self.a['unresolved']=[];self.assertTrue(qa.validate_answer(self.a,self.ev))
 def test_partial_requires_procedure_completeness_flag(self):
  del self.a['procedure_complete'];self.assertTrue(qa.validate_answer(self.a,self.ev))
 def test_partial_cannot_bypass_missing_required_source(self):
  self.assertTrue(qa.validate_verdict(self.v,self.a,{'scope':{'blocking_errors':['Missing named transcript']}}))
 def test_partial_cannot_bypass_unsupported_claim(self):
  self.v['claim_checks'][0]['supported']=False;self.assertTrue(qa.validate_verdict(self.v,self.a,{}))
 def test_full_pass_cannot_launder_partial(self):
  self.v['decision']='PASS';self.v['requested_scope_complete']=True;self.assertTrue(qa.validate_verdict(self.v,self.a,{}))
 def test_partial_pass_cannot_launder_full_answer(self):
  self.a['status']='ANSWER';self.assertTrue(qa.validate_verdict(self.v,self.a,{}))
 def test_partial_without_useful_claims_is_not_publishable(self):
  self.a['claims']=[];self.assertTrue(qa.validate_answer(self.a,self.ev))
 def test_multiple_is_not_silently_narrowed_to_two(self):
  n={'conversation_relation':'NEW','request_parts':['Configure multiple checkers'],'confirmed_context':[],'assumptions':[],'normalized_question':'Configure exactly two checkers','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':[],'search_queries':[]}
  self.assertTrue(qa.validate_normalization('Configure multiple checkers',n))
 def test_full_answer_cannot_hide_unresolved_requested_parts(self):
  self.a['status']='ANSWER';self.assertTrue(qa.validate_answer(self.a,self.ev))
 def test_missing_structured_intent_fields_is_rejected(self):
  n={'normalized_question':'Configure approvals','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':[],'search_queries':[]}
  self.assertTrue(qa.validate_normalization('Configure approvals',n))
if __name__=='__main__':unittest.main()
