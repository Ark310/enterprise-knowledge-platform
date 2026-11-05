"""Disposable SQL regression with original captured article text; no model accuracy claim."""
import os,sys,tempfile,zipfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,knowledge_topics as kt,knowledge_search as ks
import psycopg
from psycopg.rows import dict_row

def captured(path,needle):
 with zipfile.ZipFile(path) as z:
  for name in z.namelist():
   if name.replace('\\','/').endswith('evidence.json'):
    data=json.loads(z.read(name))
    rows=data if isinstance(data,list) else data.get('evidence',[])
    for row in rows:
     if needle.lower() in row.get('file','').lower():return row['text']
 raise AssertionError('Captured original not found: '+needle)

def run():
 assert os.environ.get('TD_V022_DISPOSABLE')=='YES'
 db=psycopg.connect(os.environ['TD_V022_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 profile=w.one(db,"select * from retrieval.embedding_profiles where profile_key='fixture'")
 checks=[]
 def check(ok,name):assert ok,name;checks.append(name);print('PASS QA22',name,flush=True)
 target=captured(os.environ['TD_OLD_CAPTURE'],'Error- User is not allowed to view posted entries')
 warning=captured(os.environ['TD_FAILED_CAPTURE'],'How to Turn Off Posting Warnings')
 with tempfile.TemporaryDirectory() as tmp:
  def source(rel,parts):
   path=Path(tmp)/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(parts))
   sv,_=w.register(db,{'path':str(path),'relative':rel,'role':'EXISTING_ASSET','group':'existing-assets','sha256':w.file_hash(path),'bytes':path.stat().st_size,'modified':'2026-11-05T00:00:00Z'})
   ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,is_active) values(%s,'LOCAL_PARSER','0.10.0','COMPLETE',true) returning id",(sv,))['id']
   for i,text in enumerate(parts):w.q(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256) values(%s,%s,'PASSAGE',%s,'SOURCE_TEXT',%s::jsonb,%s)",(ex,str(i),text,w.j({'file':rel}),w.sha(text)))
   db.commit();return str(sv)
  wanted=source('existing-assets/QA22/Error- User is not allowed to view posted entries/article.md',[target])
  warn=source('existing-assets/QA22/How to Turn Off Posting Warnings/article.md',[warning])
  generic='General setting permission configuration. '*30
  one=source('existing-assets/QA22/Generic setup one.pdf',[generic]*10)
  two=source('existing-assets/QA22/Generic setup copy.pdf',[generic]*10)
  rows,diag=kt.lexical(db,profile,['Post button','posting entries','setting','permission'])
  check(any(str(r['version_id'])==wanted for r in rows),'original failed terms now retrieve original posted-entries procedure through SQL stemming')
  ranked=ks.rank_pool(rows,kt.search_terms('', ['Post button','posting entries','setting','permission']))
  check(next(i for i,r in enumerate(ranked) if str(r['version_id'])==wanted)<next((i for i,r in enumerate(ranked) if str(r['version_id'])==one),999),'specific procedure outranks generic setup text')
  duplicate_rows=w.q(db,"select * from ("+__import__('retrieval_v017').base_sql('improved_hnsw',profile,True)+") b where version_id=any(%s::uuid[])",(None,None,[one,two])).fetchall()
  kt.annotate_signatures(db,profile,duplicate_rows);ids,aliases=kt.distinct_sources(duplicate_rows)
  check(len(ids)==1 and len(aliases)==1,'identical complete document text uses one optional source slot')
  revised=kt.search_terms('', ['setting','permission'],['view posted entries'],['posted entries'])
  rows,diag=kt.lexical(db,profile,revised)
  check(any(str(r['version_id'])==wanted for r in rows) and diag['terms']==['posted entries'],'verifier follow-up changes actual SQL topic search')
  check(target in [r['content_text'] for r in rows],'original citation text is retained unchanged')
  check(warn!=wanted,'conflicting warning guide remains a separate original source')

  longid=source('existing-assets/QA22/Long procedure/article.md',[('Posted entries reveal accounting details.' if i==20 else f'Unrelated background section {i}.') for i in range(40)])
  read,report=ks.read_versions(db,profile,[longid],terms=['posting entries'],morphology=True)
  check(any('Posted entries reveal' in r['content_text'] for r in read),'focused long-source reading includes inflected topic in the middle')
  for i in range(70):source(f'existing-assets/QA22/000-duplicate-{i:03}.pdf',['Post button and posted entries generic explanation.']*3)
  crowded,_=kt.lexical(db,profile,['posting entries'])
  check(any(str(r['version_id'])==wanted for r in crowded),'complete-text duplicates are removed before lexical row cap')
  generic_title=source('existing-assets/QA22/000-Generic.pdf',['Identical body with no special topic.'])
  useful_title=source('existing-assets/QA22/Zebra ledger.pdf',['Identical body with no special topic.'])
  w.q(db,"update knowledge.sources set title='Zebra ledger' where id=(select source_id from knowledge.source_versions where id=%s)",(useful_title,));db.commit()
  title_rows,_=kt.lexical(db,profile,['Zebra ledger'])
  check(any(str(r['version_id'])==useful_title for r in title_rows),'title-specific duplicate remains searchable even if alphabetical copy has generic title')
  old_profile,old_embed=w.model_profile,w.embed
  w.model_profile=lambda db,cfg:profile;w.embed=lambda cfg,text,is_query=False:[1.0]+[.01]*2559
  try:
   n={'normalized_question':'How do I view posting entries after clicking the Post button in TradeDesk?', 'keywords':['Post button','posting entries','setting','permission'],'search_queries':['Post button posting entries setting permission'],'recording_names':[],'visual_check':False}
   result=ks.collect(db,{'DataRoot':tmp},n)
   check(any(p.get('version_id')==wanted for p in result['evidence']),'complete collection and source reading retain original missing prerequisite')
   check(any(p.get('version_id')==warn for p in result['evidence']),'complete collection also retains separate posting warning guide')
  finally:w.model_profile,w.embed=old_profile,old_embed
 db.close();print('QA22 checks passed:',len(checks))
if __name__=='__main__':run()
