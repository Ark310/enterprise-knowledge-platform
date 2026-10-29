import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import module_review as m

class CoverageTests(unittest.TestCase):
 def row(self,status='COVERED'):
  return dict(topic_id='T1',coverage=status,reason='Supported reason',article_citations=[dict(unit_id='u1',excerpt='documented setting')],actions=[],unread_relevant_sources=[],limitations=[])
 def data(self):return dict(run_key='run',topics=[dict(topic=dict(topic_id='T1'),passages=[dict(id='u1',content_text='This is a documented setting.')])])
 def wrap(self,row):return m.envelope('run','DOCUMENTATION_GAP_BATCH',dict(rows=[row],limitations=[]))
 def test_valid_coverage(self):self.assertEqual(m.check_rows(self.wrap(self.row()),self.data(),['T1']),[])
 def test_covered_requires_actual_article(self):
  r=self.row();r['article_citations']=[];self.assertTrue(m.check_rows(self.wrap(r),self.data(),['T1']))
 def test_invented_excerpt_rejected(self):
  r=self.row();r['article_citations'][0]['excerpt']='invented';self.assertTrue(m.check_rows(self.wrap(r),self.data(),['T1']))
 def test_no_topic_omissions(self):self.assertTrue(m.check_rows(self.wrap(self.row()),self.data(),['T1','T2']))
 def test_duplicate_topic_rejected(self):
  obj=self.wrap(self.row());obj['payload']['rows'].append(self.row());self.assertTrue(m.check_rows(obj,self.data(),['T1']))
 def test_missing_with_unread_guide_rejected(self):
  r=self.row('NOT_FOUND_IN_REVIEWED_SOURCES');r['article_citations']=[];r['unread_relevant_sources']=['Relevant guide'];self.assertTrue(m.check_rows(self.wrap(r),self.data(),['T1']))
 def test_qualified_gap_allowed(self):
  r=self.row('NOT_FOUND_IN_REVIEWED_SOURCES');r['article_citations']=[];self.assertEqual(m.check_rows(self.wrap(r),self.data(),['T1']),[])
 def test_global_missing_enum_not_allowed(self):self.assertTrue(m.check_rows(self.wrap(self.row('MISSING_EVERYWHERE')),self.data(),['T1']))
 def test_wrong_run_rejected(self):
  obj=self.wrap(self.row());obj['run_id']='other';self.assertTrue(m.check_rows(obj,self.data(),['T1']))
 def test_index_must_account_for_every_observation(self):
  d=dict(run_key='run',observations=[dict(observation_id='S001-O1',module='User Master'),dict(observation_id='S001-O2',module='User Master')]);obj=m.envelope('run','TOPIC_INDEX',dict(topics=[dict(topic_id='T1',module='User Master',title='Time Zone',observation_ids=['S001-O1'])],limitations=[]));self.assertTrue(m.check_index(obj,d));obj['payload']['topics'][0]['observation_ids'].append('S001-O2');self.assertEqual(m.check_index(obj,d),[])
 def test_section_cannot_invent_frame_or_transcript(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'S001').mkdir();m.write(p,'module-manifest.json',dict(run_key='run'));m.write(p/'S001','evidence.json',dict(frames=[dict(source_id='1.000')],transcript=[]))
   ob=dict(observation_id='S001-O1',module='User Master',topic='Time Zone',statement='Visible setting',level='OBSERVED_VISUAL',citations=[dict(kind='FRAME',source_id='2.000',excerpt='Visible control')],unverified_points=[])
   obj=m.envelope('run','CURRENT_STATE_SECTION',dict(section_id='S001',observations=[ob],limitations=[]));self.assertTrue(m.check_section(p,obj,'S001'));ob['citations'][0]['source_id']='1.000';self.assertEqual(m.check_section(p,obj,'S001'),[])
 def test_index_cannot_silently_change_module(self):
  d=dict(run_key='run',observations=[dict(observation_id='S001-O1',module='User Master')]);obj=m.envelope('run','TOPIC_INDEX',dict(topics=[dict(topic_id='T1',module='Other',title='Time Zone',observation_ids=['S001-O1'])],limitations=[]));self.assertTrue(m.check_index(obj,d))

if __name__=='__main__':unittest.main()
