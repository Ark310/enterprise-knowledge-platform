"""Explicit disposable fixture. Identity and assembly tests, not real model accuracy."""
import os,sys,tempfile,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa,knowledge_search as ks,knowledge_scope as scope
import psycopg
from psycopg.rows import dict_row

def run():
 assert os.environ.get('TD_V021_DISPOSABLE')=='YES'
 db=psycopg.connect(os.environ['TD_V021_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc' and w.one(db,'select count(*) n from knowledge.sources')['n']<60
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'");checks=[]
 def check(ok,name):assert ok,name;checks.append(name);print('PASS QA21',name,flush=True)
 old_profile,old_embed=w.model_profile,w.embed
 w.model_profile=lambda db,cfg:profile;w.embed=lambda cfg,text,is_query=False:[1.0]+[.01]*2559
 try:
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cfg={'DataRoot':str(root)}
   def source(rel,parts,video=False):
    path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    sv,_=w.register(db,{'path':str(path),'relative':rel,'role':'CURRENT_STATE' if rel.startswith('current-state') else 'EXISTING_ASSET','group':'current-state' if rel.startswith('current-state') else 'existing-assets','sha256':w.file_hash(path),'bytes':7,'modified':'2026-11-05T00:00:00Z'})
    if parts:
     ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0','COMPLETE',true) returning id",(sv,))['id']
     for i,text in enumerate(parts):
      w.q(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds) values(%s,%s,'PASSAGE',%s,'SOURCE_TEXT',%s::jsonb,%s,%s,%s)",(ex,str(i),text,w.j({'file':rel}),w.sha(text),i*2,i*2+2))
    db.commit();return str(sv)
   rec=source('current-state/Unseen Module.mp4',[])
   srt=source('current-state/Unseen Module.srt',[f'Actual recording explanation {i}.' for i in range(18)])
   doc=source('current-state/Unseen Module_Transcript.docx',[f'Actual companion summary {i}.' for i in range(12)])
   other=source('existing-assets/Confluence Articles/unrelated/Other.srt',['new user created saved ' * 100]*10)
   n={'normalized_question':'What does Unseen Module say about creating a user?','needs_clarification':False,'clarification_question':'','changes':[],
    'search_queries':['new user created saved'],'keywords':['new user','created','saved'],'visual_check':False,'recording_names':['Unseen Module']}
   # No companion vectors: exact identity must work even if semantic search cannot return them.
   result=ks.collect(db,cfg,n)
   ev=result['evidence'];given={p.get('unit_id') for p in ev}
   check(sum(p.get('version_id')==srt for p in ev)==18 and sum(p.get('version_id')==doc for p in ev)==12,'named recording receives all 30 companion units despite irrelevant keyword hits and no companion vectors')
   check(not result['scope']['blocking_errors'],'complete companion bundle has no host coverage blockers')
   missing=scope.completeness(scope.resolve_bundle(db,cfg,n),[],[],{'requested':False})
   check(len(missing['blocking_errors'])==2,'removing companion evidence creates deterministic scope blockers')
   # Newest generic matches must not hide the older exact-name passage.
   prefix='existing-assets/Confluence Articles/tradedesk/release_notes/'
   exact=source(prefix+'Version 1.8.0.0/article.md',['NORTHSTAR BANK changed domestic format.'])
   for i in range(6):source(prefix+f'Version 3.0.{i}.0/article.md',['NORTHSTAR changed general format.'])
   web=source('existing-assets/Confluence Articles/web4/release_notes/Version 9.0.0.0/article.md',['NORTHSTAR BANK web change.'])
   n2=dict(n,normalized_question='Latest TD NORTHSTAR BANK changes?',search_queries=['NORTHSTAR BANK'],keywords=['NORTHSTAR BANK'],recording_names=[],latest_release=True)
   result=ks.collect(db,cfg,n2)
   check(any(p.get('version_id')==exact for p in result['evidence']),'older exact phrase passage retained beside six newer broad matches')
   check(not any(p.get('version_id')==web for p in result['evidence']),'Web product cannot consume TradeDesk release evidence allowance')
   check(any(a['term']=='NORTHSTAR BANK' and a['version_id']==exact for a in result['scope']['required_release_matches']),'exact phrase explicitly tracked as required evidence')
   # Real database publication checks the stored retrieval scope, not just the model verdict.
   sid,tid=str(uuid.uuid4()),str(uuid.uuid4());qa.begin(db,{'session_id':sid,'turn_id':tid,'question':'fixture'})
   passage=result['evidence'][0]
   w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,content_unit_id,source_version_id,snapshot) values(%s,%s,%s,%s,%s::jsonb)',(tid,passage['evidence_id'],passage['unit_id'],passage['version_id'],w.j(passage)))
   w.q(db,'update knowledge_qa.turns set retrieval=%s::jsonb where id=%s',(w.j({'rounds':[{'scope':missing}]}),tid));db.commit()
   answer={'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'Fixture supported claim','basis':'SOURCE','citations':[{'evidence_id':passage['evidence_id'],'excerpt':passage['text']}]}],'limitations':[]}
   verdict={'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'requested_scope_complete':True,'evidence_coverage_sufficient':True,'coverage_reason':'Narrow answer','claim_checks':[{'claim_id':'C1','supported':True,'reason':'Fixture'}],'feedback':[]}
   try:qa.finish(db,{'turn_id':tid,'status':'VERIFIED','answer':answer,'verdict':verdict});raise AssertionError('Missing scope passed')
   except ValueError as e:check('missing required source' in str(e),'stored missing-source gate blocks a model PASS at publication')
   db.rollback()
   # Duplicate recording filename must request clarification; never mix its transcript.
   source('existing-assets/Confluence Articles/Unseen Module.mp4',[])
   b=scope.resolve_bundle(db,cfg,n);check(bool(b['clarification']) and not b['required_version_ids'],'ambiguous recording identity asks for exact relative path')
 finally:w.model_profile,w.embed=old_profile,old_embed;db.close()
 print('QA21 checks passed:',len(checks));return len(checks)
if __name__=='__main__':run()
