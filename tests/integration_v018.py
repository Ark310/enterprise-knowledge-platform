"""Disposable DB only. Run after integration_v017 fixture, not an operator database.
Requires explicit TD_V018_TEST_DSN. No real Codex/Ollama calls; deterministic vectors.
"""
import os,sys,uuid,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa
import psycopg
from psycopg.rows import dict_row

def run():
 db=psycopg.connect(os.environ['TD_V018_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'")
 assert profile and w.one(db,"select count(*) n from knowledge.sources")['n']<=4,'Disposable v017 fixture required'
 assert not w.one(db,'select count(*) n from knowledge_qa.turns')['n'],'QA fixture must start empty'
 sid=str(uuid.uuid4());checks=[]
 def check(ok,name):
  assert ok,name;checks.append(name);print('PASS QA DB',name,flush=True)
 def newturn():
  tid=str(uuid.uuid4());qa.begin(db,{'session_id':sid,'turn_id':tid,'question':'How do I open user settings?'});return tid
 def verdict(answer):return {'decision':'PASS','addresses_question':True,'normalization_faithful':True,'premise_supported':True,'human_readable':True,'requested_scope_complete':True,'evidence_coverage_sufficient':True,'coverage_reason':'Fixture packet checked','claim_checks':[{'claim_id':c['id'],'supported':True,'reason':'Fixture support'} for c in answer['claims']],'feedback':[]}
 def answer(p,basis='SOURCE'):
  return {'status':'ANSWER','clarification_question':'','claims':[{'id':'C1','text':'The fixture describes user settings.','basis':basis,'citations':[{'evidence_id':p['evidence_id'],'excerpt':p['text'][:35]}]}],'limitations':['Synthetic fixture only']}
 def finish(t,a):return qa.finish(db,{'turn_id':t,'status':'VERIFIED','answer':a,'verdict':verdict(a)})
 def rejected(t,a):
  try:finish(t,a)
  except ValueError:db.rollback();return True
  return False
 original_profile=w.model_profile;original_embed=w.embed
 def vector(cfg,text,is_query=False):
  h=hashlib.sha256(text.encode()).digest();return [1.0]+[(b+1)/256 for b in h]+[0.01]*(2560-33)
 w.model_profile=lambda db,cfg:profile;w.embed=vector
 try:
  w.migration(db);w.migration(db);db.commit();check(True,'migration repeats without resetting data')
  w.q(db,"update knowledge.source_versions set lifecycle_status='ACTIVE'");db.commit()
  before=w.one(db,'select count(*) n from retrieval.content_embeddings')['n']
  t=newturn();normal={'conversation_relation':'NEW','request_parts':['Fixture requested task'],'confirmed_context':[],'assumptions':[],'normalized_question':'How do I open user settings?','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':[],'search_queries':['user settings']}
  qa.event(db,{'turn_id':t,'stage':'NORMALIZATION','payload':normal})
  ev=qa.retrieve(db,{'SearchMode':'old_exact'},{'turn_id':t,'normalization':normal})
  check(any(s['kind']=='HYBRID_HNSW' for s in ev['searches']) and all(s['diagnostics']['hnsw_index_used'] for s in ev['searches'] if s['kind']=='HYBRID_HNSW'),'QA forces actual HNSW even when inherited config says old_exact')
  check(len({p['evidence_id'] for p in ev['evidence']})==len(ev['evidence']),'multi-query evidence deduplicated with unique IDs')
  p=next(p for p in ev['evidence'] if p['kind']=='SOURCE');a=answer(p)
  qa.event(db,{'turn_id':t,'stage':'DRAFT','payload':a});qa.event(db,{'turn_id':t,'stage':'VERIFICATION','payload':verdict(a)})
  finish(t,a)
  row=w.one(db,'select * from knowledge_qa.turns where id=%s',(t,));check(row['status']=='VERIFIED' and row['answer']==a,'verified answer and normalized question persisted')
  check(w.one(db,'select count(*) n from knowledge_qa.events where turn_id=%s',(t,))['n']==3,'normalization, draft and verification audit persisted')
  check(w.one(db,'select count(*) n from retrieval.content_embeddings')['n']==before,'QA history does not contaminate source vectors')
  try:qa.event(db,{'turn_id':t,'stage':'DRAFT','payload':a});raise AssertionError('terminal event accepted')
  except ValueError:db.rollback();check(True,'terminal turns cannot be mutated with new drafts')
  t2=newturn();check(rejected(t2,a),'citation IDs from another turn cannot be reused without its evidence')
  qa.finish(db,{'turn_id':t2,'status':'FAILED','note':'Expected fixture rejection'})
  # Review-only packet isolates review freshness checks from original-source freshness.
  record=w.one(db,'select * from analysis.records limit 1');record_id=record['id'];rid=record['run_id']
  sv=w.one(db,'select id from knowledge.source_versions limit 1')['id']
  w.q(db,"insert into analysis.run_sources(run_id,source_version_id,coverage_status) values(%s,%s,'REVIEWED') on conflict do nothing",(rid,sv));db.commit()
  def reviewturn():
   t=newturn();p={'evidence_id':'R1','kind':'REVIEW','record_id':str(record_id),'text':'Saved user settings proposal','review_status':'AGENT_PROPOSED','file':'review','locator':{}}
   w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,record_id,snapshot) values(%s,%s,%s,%s::jsonb)',(t,'R1',record_id,w.j(p)));db.commit();return t,answer(p,'REVIEW_REPORT')
  t,a=reviewturn();w.q(db,"insert into analysis.human_reviews(record_id,reviewer_identity,reviewed_at,decision,rationale,evidence_uri) values(%s,'SYNTHETIC_TEST_ONLY',now(),'REJECTED','Synthetic concurrency test','fixture://not-real-review')",(record_id,));w.q(db,"update analysis.records set review_status='REJECTED' where id=%s",(record_id,));db.commit()
  check(rejected(t,a),'review rejected during answer generation cannot be published')
  qa.finish(db,{'turn_id':t,'status':'FAILED'});w.q(db,"update analysis.records set review_status='AGENT_PROPOSED' where id=%s",(record_id,));db.commit()
  t,a=reviewturn();w.q(db,"update knowledge.source_versions set lifecycle_status='SUPERSEDED' where id=%s",(sv,));db.commit()
  check(rejected(t,a),'review whose underlying source changes cannot be published')
  qa.finish(db,{'turn_id':t,'status':'FAILED'});w.q(db,"update knowledge.source_versions set lifecycle_status='ACTIVE' where id=%s",(sv,));db.commit()
  check(w.one(db,'select count(*) n from knowledge_qa.sessions where id=%s',(sid,))['n']==1,'multiple questions reuse one conversation identity')
  print('QA DATABASE INTEGRATION PASSED:',len(checks),'checks')
 finally:w.model_profile=original_profile;w.embed=original_embed;db.close()
if __name__=='__main__':run()
