"""Disposable PostgreSQL publication checks. Never run on the operator database."""
import os,sys,uuid,copy,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa
import psycopg
from psycopg.rows import dict_row

def run():
 assert os.environ.get('TD_V023_DISPOSABLE')=='YES'
 db=psycopg.connect(os.environ['TD_V023_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 sid=str(uuid.uuid4());checks=[]
 def check(ok,name):assert ok,name;checks.append(name);print('PASS QA23',name,flush=True)
 row=w.one(db,"select u.id,u.content_text,e.source_version_id from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id join knowledge.source_versions v on v.id=e.source_version_id where v.lifecycle_status='ACTIVE' and u.content_status='USABLE' limit 1")
 def turn():
  tid=str(uuid.uuid4());qa.begin(db,{'session_id':sid,'turn_id':tid,'question':'Explain the documented part and any gap.'})
  p={'evidence_id':'S1','kind':'SOURCE','unit_id':str(row['id']),'version_id':str(row['source_version_id']),'text':row['content_text'],'file':'fixture.txt','locator':{}}
  w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,content_unit_id,source_version_id,snapshot) values(%s,%s,%s,%s,%s::jsonb)',(tid,'S1',row['id'],row['source_version_id'],w.j(p)));db.commit()
  a={'status':'PARTIAL','claims':[{'id':'C1','text':'The cited source provides this documented passage.','basis':'SOURCE','citations':[{'evidence_id':'S1','excerpt':p['text'][:50]}]}],'clarification_question':'Is the other prerequisite already configured?','limitations':[],'unresolved':['Other prerequisite is not established.'],'procedure_complete':False}
  v={'decision':'PARTIAL_PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'requested_scope_complete':False,'evidence_coverage_sufficient':True,'coverage_reason':'Cited part only; remaining prerequisite explicit.','claim_checks':[{'claim_id':'C1','supported':True,'reason':'Fixture source support'}],'feedback':[]}
  return tid,a,v
 def finish(t,a,v):qa.finish(db,{'turn_id':t,'status':'VERIFIED','answer':a,'verdict':v,'note':'Verified partial; gaps remain.'})
 def reject(t,a,v):
  try:finish(t,a,v)
  except ValueError:db.rollback();return True
  return False
 t,a,v=turn();finish(t,a,v);stored=w.one(db,'select * from knowledge_qa.turns where id=%s',(t,))
 check(stored['status']=='VERIFIED' and stored['answer']['status']=='PARTIAL' and stored['verification']['decision']=='PARTIAL_PASS','approved partial stored distinctly in existing audit schema')
 check('gaps remain' in stored['completion_note'],'completion note does not imply full setup')
 t,a,v=turn();a['claims'][0]['citations'][0]['excerpt']='FABRICATED UNSEEN PASSAGE';check(reject(t,a,v),'fabricated partial citation blocked at actual database boundary')
 t,a,v=turn();v['claim_checks'][0]['supported']=False;check(reject(t,a,v),'unsupported partial blocked at database publication')
 t,a,v=turn();w.q(db,'update knowledge_qa.turns set retrieval=%s::jsonb where id=%s',(w.j({'rounds':[{'scope':{'blocking_errors':['Required transcript missing']}}]}),t));db.commit();check(reject(t,a,v),'partial cannot bypass stored required-source blocker')
 t,a,v=turn();w.q(db,"update knowledge.source_versions set lifecycle_status='SUPERSEDED' where id=%s",(row['source_version_id'],));db.commit();check(reject(t,a,v),'partial rejects evidence superseded during generation');w.q(db,"update knowledge.source_versions set lifecycle_status='ACTIVE' where id=%s",(row['source_version_id'],));db.commit()
 t,a,v=turn();v['decision']='PASS';v['requested_scope_complete']=True;check(reject(t,a,v),'partial cannot be published as a complete answer')
 # A partial answer must retain the same image-hash check as a full answer.
 with tempfile.TemporaryDirectory() as tmp:
  image=Path(tmp)/'frame.jpg';image.write_bytes(b'fixture-image-bytes')
  recording=Path(tmp)/'recording.mp4';recording.write_bytes(b'fixture-recording-bytes')
  frame=w.one(db,"select id from knowledge.poc_video_frames limit 1")
  if frame:
   t,a,v=turn();snapshot={'kind':'FRAME','evidence_id':'F2','text':'Frame descriptor only','file':'recording.mp4','path':str(image),'image_sha256':w.file_hash(image),'recording_uri':recording.as_uri(),'recording_sha256':w.file_hash(recording)}
   w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,source_version_id,frame_id,snapshot) values(%s,%s,%s,%s,%s::jsonb)',(t,'F2',row['source_version_id'],frame['id'],w.j(snapshot)));db.commit()
   image.write_bytes(b'changed');check(reject(t,a,v),'partial still rejects changed image bytes before publication')
 w.migration(db);db.commit();check(True,'v023 migration repeatable with stored full and partial answers')
 db.close();print('QA23 checks passed:',len(checks))
if __name__=='__main__':run()
