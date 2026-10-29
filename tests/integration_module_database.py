"""Opt-in synthetic whole-review persistence test. Dedicated EMPTY test DB only; never user DB.
TD_TEST_PG_CONNECTION is required. Fake embeddings test plumbing, not model accuracy.
"""
import os,sys,tempfile,json,threading,subprocess,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,module_review as m
from integration_database import FakeEmbeddingService

class ModuleDatabaseTest(unittest.TestCase):
 def test_whole_review_persistence_and_exact_results(self):
  os.environ['TD_PG_CONNECTION']=os.environ['TD_TEST_PG_CONNECTION']
  if os.environ.get('TD_TEST_PGLITE')=='1':
   def fixture_db(db):
    row=w.one(db,"select current_database() name,exists(select 1 from pg_extension where extname='vector') vector")
    if row['name']!='postgres' or not row['vector']:raise ValueError('Unexpected PGlite fixture DB')
   w.require_db=fixture_db
   def fixture_migration(db):
    fixture_db(db)
    w.q(db,(w.BASE/'database/migrations/010-local-files.sql').read_text().replace("current_database()<>'knowledge_poc'","current_database()<>'postgres'"))
   w.migration=fixture_migration
   # PGlite is a single-connection engine; avoid socket detach/reconnect races.
   import contextlib
   shared_connection=w.connect()
   @contextlib.contextmanager
   def fixture_connect():
    try:
     yield shared_connection
     shared_connection.commit()
    except:
     shared_connection.rollback();raise
   w.connect=fixture_connect
  with w.connect() as db:
   self.assertEqual(w.one(db,'select count(*) n from knowledge.sources')['n'],0,'Dedicated EMPTY test DB only')
   w.migration(db)
  service=ThreadingHTTPServer(('127.0.0.1',0),FakeEmbeddingService);threading.Thread(target=service.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    for folder,_ in w.ROOTS:(root/folder).mkdir(parents=True,exist_ok=True)
    rec=root/'current-state/demo.mp4'
    subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','color=c=blue:s=320x240:r=25','-t','3','-y',str(rec)],check=True)
    rec.with_suffix('.srt').write_text('1\n00:00:00,000 --> 00:00:02,000\nSynthetic fixture setting description.\n')
    (root/'existing-assets/Confluence Articles/demo.md').write_text('Synthetic fixture setting description. □ ₹ العربية 中文. This article explains the fixture setting.')
    cfg=dict(DataRoot=str(root),EmbeddingModel='qwen3-embedding:4b',OllamaUrl='http://127.0.0.1:'+str(service.server_port))
    self.assertEqual(w.process(cfg,{})['failed'],0)
    with w.connect() as db:start=m.start(db,cfg,dict(recording='current-state/demo.mp4'))
    work=start['work'];key=start['run_key'];packet=m.section_packet(cfg,work,'S001');cue=packet['transcript'][0]
    ob=dict(observation_id='S001-O1',module='Fixture',topic='Fixture setting',statement='Synthetic fixture setting description.',level='NARRATED_ONLY',citations=[dict(kind='TRANSCRIPT',source_id=str(cue['id']),excerpt='Synthetic fixture setting description.')],unverified_points=['Fixture only, no product claim'])
    m.write(Path(work)/'S001','a.json',m.envelope(key,'CURRENT_STATE_SECTION',dict(section_id='S001',observations=[ob],limitations=['Synthetic'])))
    topic=dict(topic_id='T1',module='Rewritten Fixture Heading',title='Fixture setting',observation_ids=['S001-O1'])
    m.write(work,'topic-index.json',m.envelope(key,'TOPIC_INDEX',dict(topics=[topic],limitations=['Synthetic'])))
    with w.connect() as db:w.q(db,"update analysis.runs set status='FAILED' where run_key=%s",(key,))
    # Reuse completed section evidence after the reproduced consolidation failure.
    import shutil
    legacy=root/'legacy/runtime/runs'/key;legacy.parent.mkdir(parents=True);shutil.move(work,legacy)
    packet=m.read(legacy/'S001','evidence.json')
    for frame in packet['frames']:frame['path']=str(legacy/Path(frame['path']).relative_to(work))
    m.write(legacy/'S001','evidence.json',packet)
    with w.connect() as db:resumed=m.resume_start(db,cfg,str(legacy))
    self.assertEqual(resumed['reused_sections'],1);work=resumed['work']
    self.assertEqual(Path(work),w.BASE/'runtime/runs'/key)
    self.assertTrue((legacy/'S001/a.json').exists()) # Original run left intact.
    self.assertTrue(Path(m.read(Path(work)/'S001','evidence.json')['frames'][0]['path']).is_file())
    with w.connect() as db:m.save_a(db,cfg,work)
    self.assertEqual(m.read(work,'agent-a.json')['payload']['topics'][0]['module'],'Fixture')
    self.assertEqual(m.read(work,'index-normalization.json')[0]['proposed_module'],'Rewritten Fixture Heading')
    with w.connect() as db:
     before=w.one(db,'select count(*) n from retrieval.analysis_embeddings')['n']
     w.q(db,"update analysis.runs set status='FAILED' where run_key=%s",(key,))
    with w.connect() as db:after_a=m.resume_start(db,cfg,work)
    self.assertEqual(after_a['checkpoint'],'A_SAVED_AND_EMBEDDED')
    with w.connect() as db:self.assertEqual(w.one(db,'select count(*) n from retrieval.analysis_embeddings')['n'],before)
    with w.connect() as db:evidence=m.retrieve(db,cfg,work)
    self.assertIn('□',w.j(evidence))
    self.assertEqual(json.loads(w.wire_result(evidence).encode('cp1252')),json.loads(w.j(evidence)))
    unit=evidence['topics'][0]['passages'][0]
    batches=Path(work)/'batches';batches.mkdir();m.write(batches,'batch-001.json',dict(topic_ids=['T1']));(batches/'batch-001').mkdir()
    row=dict(topic_id='T1',coverage='COVERED',reason='Synthetic article covers fixture.',article_citations=[dict(unit_id=str(unit['id']),excerpt='Synthetic fixture setting description.')],actions=[],unread_relevant_sources=[],limitations=['Synthetic'])
    m.write(batches/'batch-001','b.json',m.envelope(key,'DOCUMENTATION_GAP_BATCH',dict(rows=[row],limitations=['Synthetic'])))
    with w.connect() as db:report=m.finalize(db,cfg,work)
    self.assertEqual(report['summary']['COVERED'],1);self.assertEqual(report['run_key'],key)
    with w.connect() as db:
     self.assertEqual(w.one(db,'select count(*) n from retrieval.analysis_embeddings')['n'],2)
     self.assertEqual(w.one(db,'select count(distinct profile_id) n from retrieval.analysis_embeddings')['n'],1)
     self.assertEqual(w.one(db,'select count(*) n from analysis.record_links')['n'],1)
     self.assertEqual(w.one(db,'select count(*) n from analysis.record_evidence')['n'],2)
     self.assertEqual(m.results(db,key)['run_key'],key)
     self.assertEqual(m.results(db,'latest')['run_key'],key)
     self.assertEqual(w.one(db,'select count(*) n from retrieval.embedding_profiles')['n'],1)
     w.q(db,"update analysis.runs set status='FAILED' where run_key=%s",(key,));db.commit()
     with self.assertRaisesRegex(ValueError,'Existing outputs'):
      m.resume_start(db,cfg,work)
     w.q(db,"update analysis.runs set status='PARTIAL' where run_key=%s",(key,))
  finally:
   service.shutdown();service.server_close()
   if os.environ.get('TD_TEST_PGLITE')=='1':shared_connection.close()

if __name__=='__main__':unittest.main()
