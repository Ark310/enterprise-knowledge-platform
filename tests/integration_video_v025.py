"""Opt-in real video check. Requires an EMPTY disposable knowledge_poc on a separate server.
Set TD_V025_DISPOSABLE=YES, TD_V025_TEST_DSN and TD_V025_SAMPLE_DIR.
The sample directory contains the two supplied MP4/SRT pairs; FFmpeg is on PATH.
Synthetic embeddings test wiring, never live-model quality. Never use the operator database.
"""
import os,sys,uuid,tempfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa,workspace_ui as ui,video_catalog as vc

def run():
 assert os.environ.get('TD_V025_DISPOSABLE')=='YES','Explicit disposable-test authorization required'
 import psycopg
 from psycopg.rows import dict_row
 dsn=os.environ['TD_V025_TEST_DSN'];samples=Path(os.environ['TD_V025_SAMPLE_DIR'])
 db=psycopg.connect(dsn,row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 assert w.one(db,'select count(*) n from knowledge.sources')['n']==0,'Test DB must be EMPTY'
 os.environ['TD_PG_CONNECTION']=dsn;w.migration(db);db.commit()
 profile=w.one(db,"insert into retrieval.embedding_profiles(profile_key,provider,model,model_revision,dimensions,distance_metric,preprocessing_version) values('video025-fixture','OLLAMA','fixture','fixture',2560,'COSINE','fixture') returning *");db.commit()
 old_profile,old_embed=w.model_profile,w.embed;w.model_profile=lambda db,cfg:profile;w.embed=lambda cfg,text,is_query=False:[1.0]+[.01]*2559
 try:
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for folder,_ in w.ROOTS:(root/folder).mkdir(parents=True,exist_ok=True)
   dest=root/'existing-assets/VLCs/TradeDesk';dest.mkdir()
   for stem in ['Sections 3 and 4 [iuinh8jZ7J8]','Sections 5 and 6 [H232GBThOTE]']:
    for ext in ('.mp4','.srt'):shutil.copyfile(samples/(stem+ext),dest/(stem+ext))
   cfg={'DataRoot':str(root),'EmbeddingModel':'fixture','SearchMode':'improved_hnsw'}
   result=w.process(cfg,{});assert result['failed']==0,result
   assert all(v['state']=='READY' for v in vc.catalog(db,cfg)['videos'])
   repeat=w.process(cfg,{});assert repeat['embedded']==0 and repeat.get('grouped_embedded',0)==0
   for name,terms in [('Sections 3 and 4','forward drawdown'),('Sections 5 and 6','corporate client')]:
    q='Explain '+terms+' in '+name
    n=dict(normalized_question=q,needs_clarification=False,clarification_question='',changes=[],search_queries=[terms],keywords=terms.split(),recording_names=[name],visual_check=True,request_parts=[q],conversation_relation='NEW',confirmed_context=[],assumptions=[])
    chat=ui.main(db,cfg,'ui_create',{'poc':2});tid=str(uuid.uuid4());qa.begin(db,{'session_id':str(chat['id']),'turn_id':tid,'question':q})
    work=w.BASE/'runtime/video025-fixtures'/tid;work.mkdir(parents=True)
    packet=qa.retrieve(db,cfg,{'turn_id':tid,'normalization':n,'work':str(work),'web_images':True})
    assert not packet['scope']['blocking_errors'],packet['scope']
    frames=[p for p in packet['evidence'] if p['kind']=='FRAME'];assert 1<=len(frames)<=12
    assert all(name in p['file'] and Path(p['path']).is_file() for p in frames)
    show=ui.main(db,cfg,'ui_present',{'chat_id':str(chat['id']),'evidence':[frames[0]]})
    assert show['images'][0]['metadata']['recording_asset_id']
   print('PASS: real sample ingestion, no duplicate re-embedding, scoped frames and pinned playback references')
 finally:w.model_profile,w.embed=old_profile,old_embed;db.close()
if __name__=='__main__':run()
