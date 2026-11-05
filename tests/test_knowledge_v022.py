import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
class RetrievalTests(unittest.TestCase):
 def test_topic_procedure_beats_generic_settings(self):
  from knowledge_search import rank_pool
  rows=[{'id':'specific','title':'Error: User is not allowed to view posted entries','storage_uri':'a/article.md','content_text':'Click Post button to see the accounting display.','score':.03},{'id':'generic','title':'General training','storage_uri':'b.pdf','content_text':'setting permission','score':.03}]
  self.assertEqual(rank_pool(rows,['Post button','posting entries','setting','permission'])[0]['id'],'specific')
 def test_followup_replaces_generic_keywords_with_feedback_topics(self):
  from knowledge_topics import search_terms
  terms=search_terms('How to view posting entries?',['setting','permission'],['TradeDesk "posted entries" "view"'],['View Posted Entries','GL Display'])
  self.assertIn('View Posted Entries',terms);self.assertNotIn('setting',terms)
 def test_exact_body_duplicates_do_not_take_two_read_slots(self):
  from knowledge_topics import distinct_sources
  rows=[{'version_id':'a','storage_uri':'one/file.pdf','content_text':'same text','source_signature':'same'}, {'version_id':'b','storage_uri':'two/file.pdf','content_text':'same text','source_signature':'same'}, {'version_id':'c','storage_uri':'different/file.pdf','content_text':'different text'}]
  ids,report=distinct_sources(rows)
  self.assertEqual(ids,['a','c']);self.assertTrue(report)
 def test_generic_only_query_is_not_made_unsearchable(self):
  from knowledge_topics import search_terms
  self.assertTrue(search_terms('Where are settings?',['settings']))
if __name__=='__main__':unittest.main()
