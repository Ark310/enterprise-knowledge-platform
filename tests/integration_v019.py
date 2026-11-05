"""Disposable fixture only, after v017/v018. Original source corpus and real model accuracy not tested."""
import os,sys,tempfile,uuid,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_qa as qa,knowledge_search as ks
import psycopg
from psycopg.rows import dict_row

def run():
 db=psycopg.connect(os.environ['TD_V019_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'")
 assert profile and w.one(db,'select count(*) n from knowledge.sources')['n']<=4,'Disposable fixture only'
 checks=[]
 def check(ok,name):assert ok,name;checks.append(name);print('PASS QA19',name,flush=True)
 def vector(cfg,text,is_query=False):
  h=hashlib.sha256(text.encode()).digest();return [1.0]+[(b+1)/256 for b in h]+[.01]*(2560-33)
 old_profile=w.model_profile;old_embed=w.embed;w.model_profile=lambda db,cfg:profile;w.embed=vector
 try:
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);cfg={'DataRoot':str(root),'EmbeddingModel':'fixture'}
   def add(relative,text,embedded=True,status='COMPLETE',unit_start=None):
    f=root/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
    sv,ov=w.register(db,{'path':str(f),'relative':relative,'role':'EXISTING_ASSET','group':'existing-assets','sha256':w.sha(text),'bytes':len(text.encode()),'modified':'2026-11-04T00:00:00Z'})
    ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0',%s,true) returning id",(sv,status))['id']
    units=[]
    for i,part in enumerate(w.chunks(text)):
     u=w.one(db,"insert into knowledge.content_units(id,extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256) values(%s,%s,%s,'PASSAGE',%s,'SOURCE_TEXT',%s::jsonb,%s) returning id",(str(uuid.UUID(int=unit_start+i)) if unit_start is not None else str(uuid.uuid4()),ex,str(i),part,w.j({'file':relative,'line_start':i+1,'line_end':i+1}),w.sha(part)))['id'];units.append(u)
     if embedded:w.q(db,'insert into retrieval.content_embeddings(content_unit_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s)',(u,profile['id'],w.sha(part),w.vector(vector(cfg,part)),part))
    db.commit();return str(sv),units
   prefix='existing-assets/Confluence Articles/tradedesk/release_notes/Release Notes/'
   for n in range(15):add(f'existing-assets/Confluence Articles/catalog{n}/index.json','RIVERBANK release notes version '*150)
   add('existing-assets/Confluence Articles/tradedesk/release_notes/_space.json','RIVERBANK release notes '*200)
   earlier,_=add(prefix+'Version 3.0.2.0/article.md','title: Earlier\nlast_updated: 2025-01-02\nRIVERBANK format uses the old reference field.')
   current,_=add(prefix+'Version 3.0.10.0/article.md','title: Latest match\nlast_updated: 2026-07-16\nRIVERBANK adds a beneficiary reference field.\n'+'Surrounding explanation. '*300)
   add(prefix+'Version 3.0.10.0/article.json','RIVERBANK adds a beneficiary reference field.')
   later,_=add(prefix+'Version 3.0.11.0/article.md','last_updated: 2026-09-01\nUnrelated screen styling fixes.')
   missing,_=add(prefix+'Version 3.0.12.0/article.md','RIVERBANK migration guidance.',embedded=False,status='PARTIAL')
   t=str(uuid.uuid4());qa.begin(db,{'session_id':str(uuid.uuid4()),'turn_id':t,'question':'Latest RIVERBANK release changes?'})
   norm={'normalized_question':'Latest RIVERBANK release changes?','visual_check':False,'recording_names':[],'needs_clarification':False,'clarification_question':'','changes':[],'search_queries':['RIVERBANK'],'keywords':['RIVERBANK'],'include_reviews':False,'latest_release':True}
   first=qa.retrieve(db,cfg,{'turn_id':t,'normalization':norm})
   check(not any(ks.is_catalog(p['file']) for p in first['evidence']),'catalog chunks never appear as factual body evidence')
   check(not any(p['kind']=='REVIEW' for p in first['evidence']),'ordinary release question excludes unrelated saved reviews')
   check(any(str(p.get('version_id'))==current for p in first['evidence']),'target article body retrieved despite many catalogs')
   check(all(s['diagnostics']['hnsw_index_used'] for s in first['searches'] if s['kind']=='HYBRID_HNSW'),'QA19 uses actual halfvec HNSW path')
   check(any(p.get('note_last_updated')=='2026-07-16' for p in first['evidence']),'note date metadata carried into evidence')
   report=first['release_comparison'];check(not report['complete'],'partial extraction prevents claiming exhaustive release coverage')
   versions=[x['release_version'] for x in report['matches']];check(versions.index('3.0.10.0')<versions.index('3.0.2.0'),'release comparison uses numeric order')
   check(any(x['version_id']==later for x in report['later_notes']) or '3.0.12.0'==versions[0],'later release inventory represented rather than assuming top semantic result latest')
   check(any(r['version_id']==current and r['complete_usable_text'] for r in first['source_reads']),'matching article receives complete usable-text read when within budget')
   keys={p.get('unit_id',p.get('record_id')):p['evidence_id'] for p in first['evidence']}
   more=qa.retrieve(db,cfg,{'turn_id':t,'normalization':norm,'expand':True,'queries':['beneficiary reference'],'read_source_versions':[current]})
   check(all(keys[p.get('unit_id',p.get('record_id'))]==p['evidence_id'] for p in more['evidence'] if p.get('unit_id',p.get('record_id')) in keys),'expansion preserves prior citation IDs')
   try:qa.retrieve(db,cfg,{'turn_id':t,'normalization':norm,'expand':True,'queries':['again']});raise AssertionError('second expansion accepted')
   except ValueError:db.rollback();check(True,'second investigation expansion is blocked')
   diag=ks.diagnose(db,cfg,'RIVERBANK');check(any(x['matching_units']>x['embedded_matching_units'] for x in diag['matching_source_versions']),'diagnostic distinguishes text present from missing vectors')
   try:ks.collect(db,cfg,norm,read_ids=[str(uuid.uuid4())],prior=first['evidence']);raise AssertionError('unseen source ID accepted')
   except ValueError:db.rollback();check(True,'verifier cannot open arbitrary source IDs outside its packet')
   add('existing-assets/Confluence Articles/long/article.md','DEEP_TOPIC filler. '*40000,unit_start=10000)
   target,_=add('existing-assets/Confluence Articles/short/article.md','DEEP_TOPIC target instructions.',embedded=False,unit_start=(1<<128)-100)
   broad=dict(norm,normalized_question='What is DEEP_TOPIC?',keywords=['DEEP_TOPIC'],search_queries=['DEEP_TOPIC'],latest_release=False)
   selected=ks.collect(db,cfg,broad)
   check(any(p.get('version_id')==target for p in selected['evidence']),'keyword diversity before global cap preserves a short unembedded target beside a 200-plus-chunk article')
   print('V019 DATABASE PASSED:',len(checks),'checks')
 finally:w.model_profile=old_profile;w.embed=old_embed;db.close()
if __name__=='__main__':run()
