"""Captured drafts + original verifier claim checks. Contract replay, not live model evaluation."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import knowledge_qa as qa
_FIXTURE=Path(__file__).parent/'fixtures/v023/natural-runs.json'
if not _FIXTURE.exists():
 # The captured runs quote real knowledge-base articles, so they are not published.
 raise unittest.SkipTest('captured natural-run fixture not shipped (contains real KB excerpts)')
CASES=json.loads(_FIXTURE.read_text())
class CapturedNaturalRuns(unittest.TestCase):
 def test_all_eleven_natural_question_cases_accounted_for(self):
  self.assertEqual(len(CASES),11)
  self.assertEqual(sum(c['old_status']=='INSUFFICIENT_EVIDENCE' for c in CASES),6)
 def test_previously_good_captured_answers_still_validate(self):
  for c in CASES:
   if c['old_status']=='VERIFIED':
    with self.subTest(question=c['question']):
     self.assertEqual(qa.validate_answer(c['answer'],c['evidence']),[])
     self.assertEqual(qa.validate_verdict(c['verdict'],c['answer'],{}),[])
 def test_supported_rejected_drafts_can_be_independently_labelled_partial(self):
  count=0
  for c in CASES:
   if c['old_status']!='INSUFFICIENT_EVIDENCE':continue
   with self.subTest(question=c['question']):
    a,v=copy.deepcopy(c['answer']),copy.deepcopy(c['verdict'])
    if not a['claims']:
     a.update(status='PARTIAL',unresolved=['Missing evidence'],procedure_complete=False)
     self.assertTrue(qa.validate_answer(a,c['evidence']));continue
    self.assertTrue(all(x['supported'] for x in v['claim_checks']))
    a.update(status='PARTIAL',unresolved=a['limitations'] or [v['coverage_reason']],procedure_complete=False)
    v.update(decision='PARTIAL_PASS',addresses_question=True,requested_scope_complete=False,evidence_coverage_sufficient=True,retrieval_queries=[],retrieval_keywords=[],read_source_versions=[])
    # We change outcome/coverage policy ONLY; all actual source citations and original claim-support checks retained. Relevance means useful partial relevance, not old full-completeness policy.
    self.assertEqual(qa.validate_answer(a,c['evidence']),[])
    self.assertEqual(qa.validate_verdict(v,a,{}),[]);count+=1
  self.assertEqual(count,4)
 def test_captured_followup_keeps_wire_template_request(self):
  c=next(c for c in CASES if c['question']=='this is for TradeDesk')
  self.assertIn('wire templates',c['normalization']['normalized_question'].lower())
  self.assertIn('two checkers',c['normalization']['normalized_question'].lower())
 def test_captured_multiple_to_two_drift_now_blocked(self):
  c=next(c for c in CASES if c['question'].startswith('I want to create multiple'))
  n=dict(c['normalization'],conversation_relation='FOLLOW_UP',request_parts=[c['question']],confirmed_context=['TradeDesk'],assumptions=[])
  self.assertTrue(qa.validate_normalization(c['question'],n))
if __name__=='__main__':unittest.main()
