import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

class KnowledgeQaTests(unittest.TestCase):
 def test_module_exists(self):
  self.assertTrue((Path(__file__).resolve().parents[1]/'tools/knowledge_qa.py').exists())
 def test_normalization_preserves_numeric_and_named_identifiers(self):
  from knowledge_qa import validate_normalization
  good={'normalized_question':'How does TD 2.7.0.0 handle ticket #78596?','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':['spelling'],'search_queries':[]}
  self.assertEqual(validate_normalization('how dos TD 2.7.0.0 handle ticket #78596?',good),[])
  bad=dict(good,normalized_question='How does TD 2.8.0.0 handle ticket #78596?')
  self.assertTrue(validate_normalization('how dos TD 2.7.0.0 handle ticket #78596?',bad))
 def test_normalization_preserves_quoted_titles(self):
  from knowledge_qa import validate_normalization
  out={'normalized_question':'How does "Other Video" work?','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':[],'search_queries':[]}
  self.assertTrue(validate_normalization('how does "User Master" work?',out))
 def test_fabricated_quote_and_unknown_id_rejected(self):
  from knowledge_qa import validate_answer
  ev=[{'evidence_id':'S1','text':'Select the Edit button.','kind':'SOURCE','locator':{},'file':'article.md'}]
  answer={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'Select Edit.','basis':'SOURCE','citations':[{'evidence_id':'S1','excerpt':'Click Add'}]}],'limitations':[]}
  self.assertTrue(validate_answer(answer,ev))
  answer['claims'][0]['citations'][0]={'evidence_id':'S2','excerpt':'Select the Edit button.'}
  self.assertTrue(validate_answer(answer,ev))
 def test_valid_inference_requires_source_basis(self):
  from knowledge_qa import validate_answer
  ev=[{'evidence_id':'S1','text':'Select the Edit button.','kind':'SOURCE','locator':{},'file':'article.md'}]
  answer={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'This describes editing an existing record.','basis':'INFERENCE','citations':[{'evidence_id':'S1','excerpt':'Select the Edit button.'}]}],'limitations':[]}
  self.assertEqual(validate_answer(answer,ev),[])
 def test_verifier_must_check_all_claims(self):
  from knowledge_qa import validate_verdict
  a={'status':'ANSWER','claims':[{'id':'C1'},{'id':'C2'}]}
  v={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'evidence_coverage_sufficient':True,'coverage_reason':'Fixture packet checked','claim_checks':[{'claim_id':'C1','supported':True,'reason':'Supported'}],'feedback':[]}
  self.assertTrue(validate_verdict(v,a))
 def test_verifier_pass_cannot_hide_unsupported_claim(self):
  from knowledge_qa import validate_verdict
  a={'status':'ANSWER','claims':[{'id':'C1'}]}
  v={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'evidence_coverage_sufficient':True,'coverage_reason':'Fixture packet checked','claim_checks':[{'claim_id':'C1','supported':False,'reason':'Not shown'}],'feedback':[]}
  self.assertTrue(validate_verdict(v,a))
 def test_review_evidence_labelled_and_stale_excluded(self):
  from knowledge_qa import evidence_packet
  p=evidence_packet({'passages':[{'id':'u1','version_id':'v1','content_text':'Instruction','locator':{'file':'a.md'}}],'derived_findings':[{'id':'r1','statement':'Proposal','review_status':'AGENT_PROPOSED','evidence_superseded':False},{'id':'r2','statement':'Old','evidence_superseded':True}]})
  self.assertEqual(len(p),2);self.assertEqual(p[1]['kind'],'REVIEW');self.assertEqual(p[1]['review_status'],'AGENT_PROPOSED')
 def test_review_alone_cannot_be_presented_as_product_fact(self):
  from knowledge_qa import validate_answer
  ev=[{'evidence_id':'R1','kind':'REVIEW','text':'A proposed finding'}]
  a={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'The product always saves.','basis':'SOURCE','citations':[{'evidence_id':'R1','excerpt':'A proposed finding'}]}],'limitations':[]}
  self.assertTrue(validate_answer(a,ev))

if __name__=='__main__':unittest.main()
