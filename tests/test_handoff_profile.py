import unittest,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import module_review as m
class ProfileGateTests(unittest.TestCase):
 def test_b_cannot_silently_switch_embedding_profile(self):
  class DB:
   def commit(self):pass
  with tempfile.TemporaryDirectory() as td:
   m.write(td,'module-manifest.json',{'run_id':'fixture'});m.write(td,'validation-a.json',{'profile_id':'original'})
   with patch.object(m.w,'model_profile',return_value={'id':'changed'}):
    with self.assertRaisesRegex(ValueError,'Embedding profile changed'):m.store(DB(),{},td,{},'ARTICLE_REVIEW',[])
if __name__=='__main__':unittest.main()
