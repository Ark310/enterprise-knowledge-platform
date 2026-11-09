import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import knowledge_qa as q
class ChatImageTests(unittest.TestCase):
 def setUp(self):
  self.ev=[{'kind':'USER_IMAGE','evidence_id':'U1','text':'User image attached. Not product documentation.'}]
  self.a={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'An error box is visible.','basis':'VISUAL','citations':[{'evidence_id':'U1','excerpt':self.ev[0]['text']}]}],'limitations':[]}
 def test_retrieval_does_not_duplicate_uploaded_evidence(self):
  import chat_images
  items=chat_images.unique_evidence(self.ev+[{'kind':'SOURCE','evidence_id':'S2','text':'source'}]+self.ev)
  self.assertEqual([p['evidence_id'] for p in items],['U1','S2'])
 def test_user_image_supports_visible_observation(self):self.assertEqual(q.validate_answer(self.a,self.ev),[])
 def test_user_image_not_shared_product_fact(self):
  self.a['claims'][0]['basis']='SOURCE';self.assertTrue(q.validate_answer(self.a,self.ev))
 def test_unselected_image_cannot_be_illustration(self):
  self.a['illustrations']=['I99'];self.assertTrue(q.validate_answer(self.a,self.ev))
if __name__=='__main__':unittest.main()
