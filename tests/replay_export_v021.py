"""Run only in the disposable integration harness with an explicitly supplied v0.20 ZIP.
Loads SOURCE snapshots from question 4 to check question 2's exact-source lookup.
Does not validate source truth, real embedding quality, images or generated answers.
"""
import os,sys,json,zipfile,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_scope as scope,knowledge_search as ks
import psycopg
from psycopg.rows import dict_row

def run(archive):
 assert os.environ.get('TD_V021_DISPOSABLE')=='YES'
 z=zipfile.ZipFile(archive)
 questions=[]
 for n in z.namelist():
  if n.endswith('/normalization.json'):
   norm=json.loads(z.read(n));ev=json.loads(z.read(n.rsplit('/',1)[0]+'/evidence.json'));questions.append((norm,ev))
 video=next((n,e) for n,e in questions if 'successfully created and saved' in n['normalized_question'])
 password=next((n,e) for n,e in questions if "user's password" in n['normalized_question'])
 name=video[0]['recording_names'][0]
 db=psycopg.connect(os.environ['TD_V021_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc' and w.one(db,"select count(*) n from retrieval.embedding_profiles where profile_key='fixture'")['n']==1
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'")
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);cfg={'DataRoot':str(root)}
  recorded=[p for p in password[1]['evidence'] if p['kind']=='SOURCE' and p['file'].startswith('current-state/') and p['file'].endswith(('.srt','.docx'))]
  filenames=sorted({p['file'] for p in recorded});rv=next(p for p in video[1]['evidence'] if p['kind']=='FRAME')['file']
  for relative in [rv]+filenames:
   path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Replay metadata; not original media')
   sv,_=w.register(db,{'path':str(path),'relative':relative,'role':'CURRENT_STATE','group':'current-state','sha256':w.file_hash(path),'bytes':path.stat().st_size,'modified':'2026-11-05T00:00:00Z'})
   parts=[p for p in recorded if p['file']==relative]
   if parts:
    ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0','COMPLETE',true) returning id",(sv,))['id']
    for i,p in enumerate(parts):
     loc=p.get('locator',{});w.q(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds) values(%s,%s,'PASSAGE',%s,'SOURCE_TEXT',%s::jsonb,%s,%s,%s)",(ex,str(i),p['text'],w.j(loc),w.sha(p['text']),loc.get('start_seconds'),loc.get('end_seconds')))
  db.commit()
  # Remove ambiguity from synthetic Unseen Module fixture: use explicit exported identity.
  bundle=scope.resolve_bundle(db,cfg,video[0]);rows,reports=ks.read_versions(db,profile,bundle['required_version_ids'],terms=['created','saved'])
  baseline=sum(p['kind']=='SOURCE' and p['file'] in filenames for p in video[1]['evidence'])
  assert baseline==0 and len(rows)==30 and len(bundle['required_version_ids'])==2,(baseline,len(rows),bundle)
  print('EXPORT REPLAY PASSED: original Q2 supplied 0 matching units; identity-first read supplies all 30 recorded companion units from Q4. No model/vector calls.',flush=True)
 db.close()
if __name__=='__main__':run(sys.argv[1])
