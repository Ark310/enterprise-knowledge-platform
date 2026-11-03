"""Explicit disposable-database checks. Never run against operator knowledge_poc.
The caller must set TD_V017_TEST_DSN and the DB must have a fresh POC fixture schema.
No Codex or Ollama request is made: deterministic synthetic vectors isolate DB behaviour.
"""
import os,sys,tempfile,uuid,hashlib,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w, retrieval_v017 as r
from transcript_groups import ensure_grouped,VERSION
from video_evidence import frames
import psycopg
from psycopg.rows import dict_row

def run():
 dsn=os.environ['TD_V017_TEST_DSN'];db=psycopg.connect(dsn,row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 assert w.one(db,'select count(*) n from knowledge.sources')['n']==0,'Fixture must be empty; never run against a real POC database'
 checks=[]
 def check(value,name):
  assert value,name;checks.append(name);print('PASS',name,flush=True)
 w.migration(db);w.migration(db);db.commit();check(True,'additive migration is repeatable')
 profile=w.one(db,"insert into retrieval.embedding_profiles(profile_key,provider,model,model_revision,dimensions,distance_metric,preprocessing_version) values('fixture','OLLAMA','fixture','fixture',2560,'COSINE','fixture') returning *");db.commit()
 original_profile=w.model_profile;original_embed=w.embed
 def fixture_vector(cfg,text,is_query=False):
  a=hashlib.sha256(text.encode()).digest();return [1.0]+[(b+1)/256 for b in a]+[0.01]*(2560-33)
 w.model_profile=lambda db,cfg:profile;w.embed=fixture_vector
 try:
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'current-state').mkdir();(root/'existing-assets').mkdir()
   transcript=root/'current-state/demo.srt';transcript.write_text('\n\n'.join(f'{i+1}\n00:00:{i*2:02d},000 --> 00:00:{i*2+2:02d},000\nStep {i+1} opens user settings.' for i in range(20)))
   rec=root/'current-state/demo.mp4'
   subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=320x240:r=10','-t','40','-c:v','mpeg4','-y',str(rec)],check=True)
   cfg={'DataRoot':str(root),'EmbeddingModel':'fixture','SearchMode':'improved_hnsw'}
   file={'path':str(transcript),'relative':'current-state/demo.srt','role':'CURRENT_STATE','group':'current-state','sha256':w.file_hash(transcript),'bytes':transcript.stat().st_size,'modified':'2026-11-03T00:00:00Z'}
   sv,ov=w.register(db,file)
   ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0','COMPLETE',true) returning id",(sv,))
   legacy=[]
   for i,c in enumerate(w.srt_units(transcript.read_text())):
    u=w.one(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds) values(%s,%s,'PASSAGE',%s,'SUPPLIED_TRANSCRIPT',%s::jsonb,%s,%s,%s) returning id",(ex['id'],str(i),c['text'],w.j(dict(c['locator'],file=file['relative'])),w.sha(c['text']),c['start'],c['end']))['id'];legacy.append(str(u))
    v=fixture_vector(cfg,c['text']);w.q(db,'insert into retrieval.content_embeddings(content_unit_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s)',(u,profile['id'],w.sha(c['text']),w.vector(v),c['text']))
   db.commit()
   ensure_grouped(db,cfg,file,sv,ov,profile)
   grouped=w.q(db,"select u.id,u.content_text,u.locator from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id where e.processor_version=%s and u.unit_type='PASSAGE'",(VERSION,)).fetchall()
   check(grouped[0]['locator']['recording']['status']=='FILENAME_MATCH_BOUNDS_CHECKED','transcript passage pins matching recording revision and duration check')
   check(w.one(db,"select count(*) n from knowledge.source_links where relationship='TRANSCRIPT_FOR'")['n']==1,'persistent transcript-to-recording relationship')
   check(0<len(grouped)<len(legacy),'grouped passages combine original cues')
   check(w.one(db,'select count(*) n from knowledge.content_units where id=any(%s::uuid[])',(legacy,))['n']==len(legacy),'original citation IDs remain intact')
   check(w.one(db,"select count(*) n from knowledge.unit_links where relationship='DERIVED_FROM'")['n']>=len(legacy),'grouped passages link to original cues')
   count=w.one(db,'select count(*) n from knowledge.content_units')['n'];ensure_grouped(db,cfg,file,sv,ov,profile)
   check(w.one(db,'select count(*) n from knowledge.content_units')['n']==count,'retry does not duplicate grouped units')
   h=r.build_indexes(db,cfg);db.commit();check(h['hnsw_ready'],'both halfvec HNSW indexes are valid at 2560 dimensions')
   vec=w.vector(fixture_vector(cfg,'user settings'))
   old=r.execute(db,profile,'user settings',vec,'old_exact',None,10)
   improved=r.execute(db,profile,'user settings',vec,'improved_exact',None,10)
   check(all(str(p['id']) in legacy for p in old['passages']),'legacy mode uses original cues')
   check(all(str(p['id']) not in legacy for p in improved['passages']),'improved mode selects grouped passages')
   check(not improved['diagnostics']['hnsw_index_used'],'exact baseline does not use ANN index')
   db.commit();report=r.compare(db,cfg,'user settings',None,10)
   check(report['modes']['improved_hnsw']['hnsw_index_used'],'comparison query really uses source HNSW index')
   check(Path(report['report_json']).exists() and Path(report['report_markdown']).exists(),'comparison exports both reports')
   # Remove one alternate vector: improved eligibility must revert to complete original cue extraction.
   w.q(db,'delete from retrieval.content_embeddings where content_unit_id=%s',(grouped[0]['id'],));db.commit()
   incomplete=r.execute(db,profile,'user settings',vec,'improved_exact',None,10)
   check(all(str(p['id']) in legacy for p in incomplete['passages']),'incomplete grouped vectors fall back to original cues')
   db.commit()
   try:r.compare(db,cfg,'user settings',None,10);raise AssertionError('comparison should require ready grouped transcripts')
   except ValueError as e:check('No grouped transcripts' in str(e),'comparison blocks misleading all-baseline fallback')
   db.rollback();ensure_grouped(db,cfg,file,sv,ov,profile)
   vf=dict(file,path=str(rec),relative='current-state/demo.mp4',sha256=w.file_hash(rec),bytes=rec.stat().st_size);video_sv,video_ov=w.register(db,vf);db.commit()
   first=frames(db,cfg,rec,0,3);db.commit();second=frames(db,cfg,rec,0,3);db.commit()
   check(all(f['cache_reused'] for f in second),'second review reuses hash-verified frames')
   check([x['frame_id'] for x in first]==[x['frame_id'] for x in second],'frame IDs and actual timestamps remain stable')
   check(w.one(db,'select count(*) n from knowledge.poc_video_frames')['n']==len(first),'frame metadata deduplicates')
   Path(first[0]['path']).write_bytes(b'corrupted')
   repaired=frames(db,cfg,rec,0,3);db.commit();check(not repaired[0]['cache_reused'],'corrupt frame cache is regenerated')
   rid=w.one(db,"insert into analysis.runs(run_key,module,topic,question,contract_version,agent_a_version,agent_b_version,status) values('fixture','fixture','fixture','fixture','fixture','fixture','fixture','PARTIAL') returning id")['id']
   output=w.one(db,"insert into analysis.agent_outputs(run_id,agent_role,output_json,schema_validated,validation_status) values(%s,'CURRENT_STATE','{}',true,'VALID') returning id",(rid,))['id']
   record=w.one(db,"insert into analysis.records(run_id,agent_output_id,record_key,record_type,topic,statement) values(%s,%s,'fixture','OBSERVATION','fixture','user settings') returning id",(rid,output))['id']
   w.q(db,'insert into retrieval.analysis_embeddings(record_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s)',(record,profile['id'],w.sha('user settings'),vec,'user settings'));db.commit()
   w.q(db,'SET LOCAL enable_seqscan=off');w.q(db,'SET LOCAL enable_sort=off')
   findings,details=r.derived_search(db,profile,vec,'improved_hnsw')
   check(details['hnsw_index_used'] and findings[0]['id']==record,'saved findings use analysis HNSW candidate search and full-vector reranking')
   from video_evidence import link
   link(db,record,{'source_id':second[0]['source_id']},second);link(db,record,{'source_id':second[0]['source_id']},second);db.commit()
   check(w.one(db,'select count(*) n from analysis.poc_frame_evidence')['n']==1,'visual finding stores one explicit reusable frame link')
   check(not r.execute(db,profile,'user settings',vec,'improved_hnsw','EXISTING_ASSET',10,force_ann=True)['passages'],'role filter excludes current-state passages')
   db.commit()
   # Restrict current source version: both modes must exclude it.
   w.q(db,"update knowledge.source_versions set lifecycle_status='SUPERSEDED' where id=%s",(sv,));db.commit()
   empty=r.execute(db,profile,'user settings',vec,'improved_hnsw',None,10,force_ann=True)
   check(not empty['passages'],'superseded source revisions do not enter results')
   print('INTEGRATION PASSED:',len(checks),'checks; PostgreSQL',db.info.server_version,'pgvector',h['pgvector'])
 finally:w.model_profile=original_profile;w.embed=original_embed;db.close()
if __name__=='__main__':run()
