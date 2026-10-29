import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import module_review as m
class IndexNormalizationTests(unittest.TestCase):
 def data(self,modules=('System Admin >> Security >> User Master',)):
  return dict(run_key='run',observations=[dict(observation_id=f'S001-O{i+1}',module=module,statement='Original fact') for i,module in enumerate(modules)])
 def index(self,refs):return m.envelope('run','TOPIC_INDEX',dict(topics=[dict(topic_id='T7',module='Rewritten module heading',title='Recorded settings',observation_ids=refs)],limitations=[]))
 def test_renamed_heading_uses_original_attribution(self):
  d=self.data();original=json.dumps(d);obj=self.index(['S001-O1']);normalized,audit=m.normalize_index(obj,d)
  self.assertEqual(normalized['payload']['topics'][0]['module'],d['observations'][0]['module']);self.assertEqual(m.check_index(normalized,d),[]);self.assertEqual(json.dumps(d),original);self.assertEqual(audit[0]['proposed_module'],'Rewritten module heading')
 def test_original_proposal_not_silently_overwritten(self):
  obj=self.index(['S001-O1']);before=json.dumps(obj);m.normalize_index(obj,self.data());self.assertEqual(json.dumps(obj),before)
 def test_navigation_separator_case_and_spacing_only(self):
  d=self.data(('System Admin >> Security >> User Master',' system admin / security / USER MASTER '));obj,audit=m.normalize_index(self.index(['S001-O1','S001-O2']),d);self.assertEqual(len(obj['payload']['topics']),1);self.assertEqual(m.check_index(obj,d),[])
 def test_distinct_modules_are_split(self):
  d=self.data(('User Master','Payments'));obj,audit=m.normalize_index(self.index(['S001-O1','S001-O2']),d);self.assertEqual(len(obj['payload']['topics']),2);self.assertEqual([x['module'] for x in obj['payload']['topics']],['User Master','Payments']);self.assertEqual(m.check_index(obj,d),[]);self.assertTrue(all(x['split'] for x in audit))
 def test_unknown_observation_still_rejected(self):
  with self.assertRaises(ValueError):m.normalize_index(self.index(['invented']),self.data())
 def test_duplicate_observation_still_rejected(self):
  with self.assertRaises(ValueError):m.normalize_index(self.index(['S001-O1','S001-O1']),self.data())
 def test_omitted_observation_still_rejected(self):
  with self.assertRaises(ValueError):m.normalize_index(self.index(['S001-O1']),self.data(('User Master','User Master')))
if __name__=='__main__':unittest.main()
