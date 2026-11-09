import sys,tempfile,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
class WorkspaceTests(unittest.TestCase):
 def test_upload_is_image_and_normalized(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'in.png';Image.new('RGB',(32,24),'blue').save(p)
   out=u.normalize_upload(p.read_bytes(),Path(tmp)/'out.png')
   self.assertEqual(out['width'],32);self.assertTrue(out['sha256'])
 def test_non_image_rejected(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):u.normalize_upload(b'<script>bad</script>',Path(tmp)/'x.png')
 def test_path_traversal_and_symlink_rejected(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'root';root.mkdir();outside=Path(tmp)/'secret.txt';outside.write_text('secret')
   self.assertIsNone(u.safe_file(root,'../secret.txt'))
   (root/'link').symlink_to(outside);self.assertIsNone(u.safe_file(root,'link'))
 def test_article_images_resolve_only_local_linked_files(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'images').mkdir();Image.new('RGB',(32,24),'blue').save(root/'images/a.png')
   article=root/'article.md';article.write_text('![Settings](images/a.png)\n![Remote](https://example.com/a.png)\n![Bad](../secret.png)')
   rows=u.linked_images(root,article)
   self.assertEqual(len(rows),1);self.assertEqual(rows[0]['label'],'Settings')
 def test_article_html_image_and_parent_folder_link(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'page').mkdir();(root/'images').mkdir();Image.new('RGB',(20,20),'blue').save(root/'images/a.png')
   p=root/'page/article.md';p.write_text('<img src="../images/a.png">')
   self.assertEqual(len(u.linked_images(root,p)),1)
 def test_original_article_screenshot_fallback(self):
  import workspace_ui as u
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'article.md';p.write_text('An article without an image link.')
   Image.new('RGB',(20,20),'blue').save(root/'screenshot.png')
   self.assertEqual(u.linked_images(root,p)[0]['label'],'Article screenshot')
if __name__=='__main__':unittest.main()
