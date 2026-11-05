"""Disposable-only QA20 SQL/frame checks. Runs after fixture integration_v017/018/019."""
import os,sys,tempfile,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa,knowledge_search as ks,knowledge_visual as kv
import psycopg
from psycopg.rows import dict_row

def run():
 db=psycopg.connect(os.environ['TD_V020_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert os.environ.get('TD_V020_DISPOSABLE')=='YES' and db.info.dbname=='knowledge_poc' and w.one(db,'select count(*) n from knowledge.sources')['n']<50,'Disposable fixture only'
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'");checks=[]
 def check(value,name):assert value,name;checks.append(name);print('PASS QA20',name,flush=True)
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);(root/'current-state').mkdir();cfg={'DataRoot':str(root)}
  rec=root/'current-state/Review Sample.mp4'
  subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=320x240:r=10','-t','4','-c:v','mpeg4','-y',str(rec)],check=True)
  def register(path):
   return w.register(db,{'path':str(path),'relative':path.relative_to(root).as_posix(),'role':'CURRENT_STATE','group':'current-state','sha256':w.file_hash(path),'bytes':path.stat().st_size,'modified':'2026-11-05T00:00:00Z'})[0]
  rv=register(rec);srt=rec.with_suffix('.srt');srt.write_text('fixture');sv=register(srt)
  ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0','COMPLETE',true) returning id",(sv,))['id']
  for i in range(50):
   text='save completed' if i==40 else 'other explanation'
   w.q(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds) values(%s,%s,'PASSAGE',%s,'SUPPLIED_TRANSCRIPT',%s::jsonb,%s,%s,%s)",(ex,str(i),text,w.j({'file':'current-state/Review Sample.srt'}),w.sha(text),i/20,(i+1)/20))
  db.commit()
  rows,report=ks.read_versions(db,profile,[sv],terms=['save'])
  keys={p['unit_key'] for p in rows}
  check({'39','40','41','49','0'}<=keys,'late question hit, neighbours and both ends supplied')
  check(len(rows)<=24 and not report[0]['complete_usable_text'],'long-source read bounded and incomplete disclosed')
  w.q(db,'delete from knowledge.content_units where extraction_id=%s and unit_key::integer>=18',(ex,));db.commit()
  rows,report=ks.read_versions(db,profile,[sv],terms=['save'])
  check(len(rows)==18 and report[0]['complete_usable_text'],'18-unit transcript read completely instead of prefix 12')
  norm={'visual_check':True,'recording_names':['Review Sample'],'keywords':['save']}
  frames,visual=kv.prepare(db,cfg,norm,rows)
  check(visual['recordings'][0]['status']=='SAMPLED' and 1<=len(frames)<=12,'real FFmpeg samples registered from exact named recording')
  check(all(p['version_id']==str(rv) and 0<=p['locator']['start_seconds']<4 for p in frames),'every visual sample pins original video and bounded timestamp')
  ev=ks.merge_evidence([],frames);kv.stage_images(ev,root/'run')
  check(all(Path(p['path']).is_file() for p in ev),'run-local images exported reproducibly')
  sid,tid=str(uuid.uuid4()),str(uuid.uuid4());qa.begin(db,{'session_id':sid,'turn_id':tid,'question':'What is visible?'})
  f=ev[0]
  w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,source_version_id,frame_id,snapshot) values(%s,%s,%s,%s,%s::jsonb)',(tid,f['evidence_id'],rv,f['frame_id'],w.j(f)));db.commit()
  check(True,'additive evidence constraint accepts pinned frame FK')
  ans={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','basis':'VISUAL','text':'Synthetic blue test frame','citations':[{'evidence_id':f['evidence_id'],'excerpt':f['text']}]}],'limitations':['Synthetic fixture only']}
  verdict={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'evidence_coverage_sufficient':True,'coverage_reason':'Synthetic fixture','claim_checks':[{'claim_id':'C1','supported':True,'reason':'Synthetic fixture'}],'feedback':[]}
  check(not qa.validate_answer(ans,ev),'visual frame citation accepted without fabricating transcript quotation')
  # Exercise the real retrieve → snapshot → publish boundary with actual frame FKs.
  full=str(uuid.uuid4());qa.begin(db,{'session_id':sid,'turn_id':full,'question':'Show Review Sample save outcome'})
  normalization={'normalized_question':'Show Review Sample save outcome','needs_clarification':False,'clarification_question':'','changes':[],
   'search_queries':['save outcome'],'keywords':['save'],'visual_check':True,'recording_names':['Review Sample']}
  old_profile,old_embed=w.model_profile,w.embed
  try:
   w.model_profile=lambda db,cfg:profile;w.embed=lambda cfg,text,is_query=False:[1.0]+[.01]*2559
   packet=qa.retrieve(db,cfg,{'turn_id':full,'normalization':normalization,'work':str(root/'full-run')})
  finally:w.model_profile,w.embed=old_profile,old_embed
  saved=w.one(db,'select count(*) n from knowledge_qa.evidence where turn_id=%s and frame_id is not null',(full,))['n']
  supplied=[p for p in packet['evidence'] if p['kind']=='FRAME']
  check(saved==len(supplied)>0,'real QA retrieval persists every shared image snapshot with frame FK')
  real=supplied[0];complete=dict(ans,claims=[dict(ans['claims'][0],citations=[{'evidence_id':real['evidence_id'],'excerpt':real['text']}])])
  qa.finish(db,{'turn_id':full,'status':'VERIFIED','answer':complete,'verdict':verdict})
  check(w.one(db,'select status from knowledge_qa.turns where id=%s',(full,))['status']=='VERIFIED','untampered visual answer passes complete audit publication boundary')
  Path(f['path']).write_bytes(b'changed')
  try:qa.finish(db,{'turn_id':tid,'status':'VERIFIED','answer':ans,'verdict':verdict});raise AssertionError('Tamper passed')
  except ValueError as e:check('Frame evidence changed' in str(e),'changed image prevents final publication')
  db.rollback()
  no,rep=kv.prepare(db,cfg,dict(norm,recording_names=['Review Sample Advanced']),rows)
  check(not no and rep['recordings'][0]['matching_recordings']==0,'similar but wrong recording never substituted')
  rec2=root/'other/Review Sample.mp4';rec2.parent.mkdir();rec2.write_bytes(rec.read_bytes());register(rec2);db.commit()
  no,rep=kv.prepare(db,cfg,norm,rows)
  check(not no and rep['recordings'][0]['matching_recordings']==2,'duplicate basename requires clarification')
  w.migration(db);db.commit();check(True,'visual migration repeatable with stored frame audit rows')
 db.close();print('QA20 checks passed:',len(checks));return len(checks)
if __name__=='__main__':run()
