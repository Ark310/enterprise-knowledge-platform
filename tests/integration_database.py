"""Opt-in synthetic integration test. Requires a dedicated EMPTY knowledge_poc test DB, never production."""
import os,sys,tempfile,json,threading,unittest,zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w
class FakeEmbeddingService(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'models':[{'name':'qwen3-embedding:4b','digest':'SYNTHETIC-TEST-DIGEST'}]}).encode())
 def do_POST(self):
  json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.send_response(200);self.end_headers();self.wfile.write(b'{"embeddings":[[0.1,0.2,0.3]]}')
 def log_message(self,*args):pass
class DatabaseTests(unittest.TestCase):
 def test_ingest_retry_search_api_and_local_constraints(self):
  self.assertTrue(os.environ.get('TD_TEST_PG_CONNECTION'),'Dedicated synthetic DB connection required')
  os.environ['TD_PG_CONNECTION']=os.environ['TD_TEST_PG_CONNECTION']
  with w.connect() as db:
   self.assertEqual(w.one(db,'select count(*) n from knowledge.sources')['n'],0,'Test DB must be EMPTY')
   w.migration(db);w.migration(db)
  service=ThreadingHTTPServer(('127.0.0.1',0),FakeEmbeddingService);threading.Thread(target=service.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d)
    for folder,_ in w.ROOTS:(root/folder).mkdir(parents=True,exist_ok=True)
    (root/'current-state/demo.srt').write_text('1\n00:08:15,000 --> 00:08:20,000\nTwo Factor Authentication options include TOTP.\n')
    (root/'existing-assets/Confluence Articles/demo.md').write_text('User Master Authentication Type settings and TOTP guidance.')
    (root/'existing-assets/REST API/page.json').write_text(json.dumps({'kind':'endpoint','content':{'text':'POST /user authentication'},'endpoint':{'method':'POST','path':'/user','headers':[{'name':'Authorization','required':True,'children':[]}],'responses':[{'status':'2011','example':'{}','params':[]}]}}))
    (root/'existing-assets/Sharepoint/example.snag').write_bytes(b'\xcbTSC SNAGN')
    with zipfile.ZipFile(root/'current-state/demo_Transcript.docx','w') as z:
     z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DOCX transcript: Authentication Type includes TOTP.</w:t></w:r></w:p></w:body></w:document>')
    cfg={'DataRoot':str(root),'EmbeddingModel':'qwen3-embedding:4b','OllamaUrl':'http://127.0.0.1:'+str(service.server_port)}
    first=w.process(cfg,{});self.assertEqual(first['failed'],0,first);self.assertEqual(first['embedded'],4);self.assertEqual(first['blocked'],1)
    second=w.process(cfg,{});self.assertEqual(second['failed'],0,second);self.assertEqual(second['embedded'],0)
    with w.connect() as db:
     self.assertEqual(w.one(db,'select count(*) n from knowledge.sources')['n'],5)
     self.assertEqual(w.one(db,'select count(*) n from knowledge.source_versions')['n'],5)
     self.assertEqual(w.one(db,'select count(*) n from knowledge.api_operations')['n'],1)
     status=w.one(db,'select status_label_raw,http_status from knowledge.api_examples');self.assertEqual(status['status_label_raw'],'2011');self.assertIsNone(status['http_status'])
     results=w.search(db,cfg,'Authentication','CURRENT_STATE');self.assertEqual(len(results['passages']),2)
     try:
      with db.transaction():db.execute("insert into knowledge.storage_objects(group_id,object_key,object_kind,title,drive_file_id) select id,'bad-local','LOCAL_FILE','bad','fake' from knowledge.source_groups limit 1")
     except Exception:pass
     else:self.fail('Fake Drive ID accepted for LOCAL_FILE')
    with w.connect() as db:
     with db.transaction(force_rollback=True):
      for ext in ['docx','doc','pdf','srt','mp4','wmv','md','html','json','xlsx','xls','png','jpg','snag','cs','txt']:
       w.q(db,"insert into knowledge.sources(source_system,external_namespace,external_key,source_type,title) values('CATEGORY_TEST','category',%s,%s,%s)",(ext,w.source_type('sample.'+ext),ext))
     self.assertEqual(w.one(db,"select source_type from knowledge.sources where title='demo_Transcript.docx'")['source_type'],'DOCUMENT')
    # Malformed output must be retained as INVALID, never throw before the validation report.
    with tempfile.TemporaryDirectory() as run_dir:
     work=Path(run_dir);req=json.loads((w.BASE/'tests/scenarios/T02-original.json').read_text());req['run_id']='SYNTHETIC-INVALID-OUTPUT'
     (work/'evidence-a.json').write_text(json.dumps({'request':req,'transcript_file':'demo.srt','transcript':[],'frames':[]}));(work/'prompt-a.txt').write_text('synthetic validation fixture');(work/'bad.json').write_text('[]')
     with w.connect() as db:
      w.q(db,"insert into analysis.runs(run_key,module,topic,question,contract_version,agent_a_version,agent_b_version,status) values(%s,'test','test','test','td-doc-review-2.0','test','test','PROCESSING')",(req['run_id'],))
      result=w.save_output(db,cfg,{'work':str(work),'role':'CURRENT_STATE','output':str(work/'bad.json')});self.assertFalse(result['valid']);self.assertTrue((work/'validation-a.json').exists())
     with w.connect() as db:self.assertEqual(w.one(db,"select validation_status from analysis.agent_outputs")['validation_status'],'INVALID')
    (root/'existing-assets/Confluence Articles/demo.md').write_text('Updated Authentication Type settings.')
    third=w.process(cfg,{});self.assertEqual(third['failed'],0,third)
    with w.connect() as db:
     self.assertEqual(w.one(db,'select count(*) n from knowledge.source_versions')['n'],6)
     self.assertEqual(w.one(db,"select count(*) n from knowledge.source_versions where lifecycle_status='SUPERSEDED'")['n'],1)
  finally:service.shutdown();service.server_close()
if __name__=='__main__':unittest.main()
