import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
class KnowledgeSearchTests(unittest.TestCase):
 def test_search_module_exists(self):self.assertTrue((Path(__file__).resolve().parents[1]/'tools/knowledge_search.py').exists())
 def test_catalogs_not_body_evidence(self):
  from knowledge_search import is_catalog
  self.assertTrue(is_catalog('file:///C:/Data/index.json'));self.assertTrue(is_catalog('file:///C:/Data/_space.json'));self.assertFalse(is_catalog('file:///C:/Data/Version%203.0.2.1/article.md'))
 def test_export_family_deduplicates_markdown_json(self):
  from knowledge_search import family
  self.assertEqual(family('file:///C:/x/Topic/article.json'),family('file:///C:/x/Topic/article.md'))
 def test_rank_diversity_caps_same_article(self):
  from knowledge_search import diverse
  rows=[{'id':str(i),'storage_uri':'file:///a/article.md','content_text':'x'} for i in range(8)]+[{'id':'other','storage_uri':'file:///b/article.md','content_text':'y'}]
  out=diverse(rows,limit=5,per_source=2);self.assertEqual(len(out),3);self.assertIn('other',[r['id'] for r in out])
 def test_version_order_numeric_not_lexical(self):
  from knowledge_search import release_version
  self.assertGreater(release_version('Release Notes/Version 3.0.10.0/article.md'),release_version('Release Notes/Version 3.0.2.9/article.md'))
 def test_version_prefers_leaf(self):
  from knowledge_search import release_version
  self.assertEqual(release_version('Release Notes/Version 3.0.0.0/Version 3.0.2.1/article.md'),(3,0,2,1))
 def test_keywords_are_focused_and_regex_escaped(self):
  from knowledge_search import keywords,keyword_pattern
  terms=keywords('Latest Woodgrove Bank TD changes',['Woodgrove','Woodgrove','release notes'])
  self.assertIn('Woodgrove',terms);self.assertIn('Woodgrove',terms);self.assertNotIn('release notes',terms);self.assertNotIn('x.*',keyword_pattern(['x.*']))
 def test_snapshot_keeps_ids_on_expansion(self):
  from knowledge_search import merge_evidence
  old=[{'evidence_id':'S1','kind':'SOURCE','unit_id':'a','text':'old'}]
  new=[{'evidence_id':'S1','kind':'SOURCE','unit_id':'b','text':'new'},{'evidence_id':'S2','kind':'SOURCE','unit_id':'a','text':'old'}]
  out=merge_evidence(old,new);self.assertEqual([x['evidence_id'] for x in out],['S1','S2']);self.assertEqual(out[1]['unit_id'],'b')
 def test_byte_budget_never_slices_citable_text(self):
  from knowledge_search import merge_evidence
  rows=[{'kind':'SOURCE','unit_id':'a','text':'x'*10},{'kind':'SOURCE','unit_id':'b','text':'y'*10}]
  out=merge_evidence([],rows,char_budget=15);self.assertEqual(len(out),1);self.assertEqual(out[0]['text'],'x'*10)
 def test_short_non_entity_question_still_gets_content_keywords(self):
  from knowledge_search import keywords
  self.assertIn('password',keywords('how do i change my password',['password']))
 def test_specific_topic_hits_rank_above_generic_topic_hits(self):
  from knowledge_search import rank_pool
  rows=[{'id':'a','storage_uri':'a.md','title':'General','content_text':'user'},{'id':'b','storage_uri':'b.md','title':'Reset password','content_text':'user password change'}]
  self.assertEqual(rank_pool(rows,['user','password','change'])[0]['id'],'b')
 def test_latest_version_request_cannot_skip_chronology_due_to_missing_plan_flag(self):
  from knowledge_search import wants_chronology
  self.assertTrue(wants_chronology({'normalized_question':'Which version contains the latest bank changes?'}))
  self.assertFalse(wants_chronology({'normalized_question':'How do I reset a password?'}))
if __name__=='__main__':unittest.main()
