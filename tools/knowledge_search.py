"""QA-specific bounded investigation. Reuses vectors; no file execution or guessed product facts."""
import re,json,uuid,urllib.parse,datetime
from collections import Counter
import worker as w
import retrieval_v017 as r

STOP={'td','tradedesk','release','notes','release notes','version','versions','latest','changes','change','dates','date','article','articles','documentation','imported','dataset','most recent'}
def is_catalog(path):return urllib.parse.unquote(path).replace('\\','/').lower().rsplit('/',1)[-1] in {'index.json','index.md','_space.json'}
def family(path):
 path=urllib.parse.unquote(path).replace('\\','/').lower()
 return re.sub(r'/article\.(json|md)$','/article',path)
def release_version(path):
 found=re.findall(r'\bVersion[ +]?(\d+(?:\.\d+){1,4})',urllib.parse.unquote(path),re.I)
 return tuple(map(int,found[-1].split('.'))) if found else ()
def keywords(question,proposed):
 values=list(proposed)+re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b',question)
 out=[]
 for value in values:
  term=value.strip()
  if not 2<=len(term)<=100 or term.lower() in STOP:continue
  if term.lower() not in [x.lower() for x in out]:out.append(term)
 return out[:8]
def wants_chronology(normalized):
 q=normalized['normalized_question']
 return normalized.get('latest_release',False) or bool(re.search(r'\b(latest|newest|most recent)\b',q,re.I) and re.search(r'\b(version|release)',q,re.I))
def keyword_pattern(terms):return '(?:'+'|'.join(re.escape(x) for x in terms)+')' if terms else r'(?!)'
def diverse(rows,limit=24,per_source=3):
 counts=Counter();out=[];seen=set()
 for row in rows:
  key=family(row.get('storage_uri',row.get('locator',{}).get('file','')))
  # Prefer one physical rendition for each article. Other chunks from its chosen rendition remain eligible.
  uri=row.get('storage_uri',row.get('locator',{}).get('file',''))
  selected=next((x.get('storage_uri',x.get('locator',{}).get('file','')) for x in out if family(x.get('storage_uri',x.get('locator',{}).get('file','')))==key),uri)
  if uri!=selected or counts[key]>=per_source or str(row['id']) in seen:continue
  counts[key]+=1;seen.add(str(row['id']));out.append(row)
  if len(out)>=limit:break
 return out

def rank_pool(rows,terms):
 best={}
 for row in rows:
  body=row['content_text'].casefold();title=row.get('title','').casefold()
  relevance=sum((3 if term.casefold() in title else 0)+(1 if term.casefold() in body else 0) for term in terms)+25*row.get('score',0)
  key=str(row['id'])
  if key not in best or relevance>best[key][0]:best[key]=(relevance,row)
 return [p for _,p in sorted(best.values(),key=lambda item:(-item[0],not item[1].get('storage_uri','').endswith('/article.md'),str(item[1]['id'])))]

def merge_evidence(old,new,char_budget=100000,max_items=80):
 out=[dict(p) for p in old];seen={(p['kind'],str(p.get('unit_id',p.get('record_id')))) for p in out};used=sum(len(p['text']) for p in out)
 for p in new:
  key=(p['kind'],str(p.get('unit_id',p.get('record_id'))))
  if key in seen:continue
  if len(out)>=max_items or used+len(p['text'])>char_budget:continue
  p=dict(p,evidence_id=('S' if p['kind']=='SOURCE' else 'R')+str(len(out)+1));out.append(p);seen.add(key);used+=len(p['text'])
 return out

def enrich(db,rows):
 ids=list({str(p['version_id']) for p in rows})
 meta={str(v['id']):v for v in w.q(db,'select id,source_modified_at,metadata from knowledge.source_versions where id=any(%s::uuid[])',(ids,)).fetchall()} if ids else {}
 for p in rows:
  v=meta.get(str(p['version_id']),{});p['source_metadata']=v.get('metadata',{});p['source_modified_at']=str(v.get('source_modified_at') or '')
  p['release_version']='.'.join(map(str,release_version(p.get('storage_uri','')))) or None
  m=re.search(r'(?im)^\s*last_updated\s*:\s*["\x27]?([^\r\n"\x27]+)',p['content_text'])
  if not m:m=re.search(r'"last_updated"\s*:\s*"([^"]+)"',p['content_text'])
  p['note_last_updated']=m.group(1).strip() if m else None
 return rows

def read_versions(db,profile,version_ids,per_version=12):
 base=r.base_sql('improved_hnsw',profile,True);out=[];reports=[]
 for version_id in list(dict.fromkeys(str(uuid.UUID(str(x))) for x in version_ids))[:8]:
  total=w.one(db,f'WITH b AS ({base}) select count(*) n from b where version_id=%s',(None,None,version_id))['n']
  rows=w.q(db,f"""WITH b AS ({base}) select * from b where version_id=%s
   order by coalesce(start_seconds,0),case when unit_key ~ '^[0-9]+$' then unit_key::numeric else 0 end,unit_key limit %s""",(None,None,version_id,per_version)).fetchall()
  out.extend(rows);reports.append({'version_id':version_id,'usable_units_total':total,'units_read':len(rows),'complete_usable_text':bool(total) and total==len(rows)})
 return out,reports

def chronology(db,profile,terms):
 if not terms:return [],{'requested':True,'complete':False,'reason':'No focused topic keywords; cannot establish a latest matching release.'}
 base=r.base_sql('improved_hnsw',profile,True);pattern=keyword_pattern(terms)
 rows=w.q(db,f"""WITH b AS ({base}) select v.id version_id,v.storage_uri,s.title,v.source_modified_at,
  count(b.id) usable_units,count(b.id) filter(where b.content_text ~* %s) matching_units,
  exists(select 1 from knowledge.extractions ex where ex.source_version_id=v.id and ex.is_active and ex.status<>'COMPLETE') incomplete_extraction
  from knowledge.source_versions v join knowledge.sources s on s.id=v.source_id left join b on b.version_id=v.id
  where v.lifecycle_status='ACTIVE' and lower(v.storage_uri) like '%%/release_notes/%%'
  and lower(v.storage_uri) ~ '/article[.](md|json)$'
  group by v.id,s.title order by v.storage_uri,v.id limit 1001""",(None,None,pattern)).fetchall()
 truncated=len(rows)>1000;rows=rows[:1000]
 # Deduplicate physical Markdown/JSON exports. Prefer a readable body over a missing body.
 groups={}
 for p in rows:
  key=family(p['storage_uri']);old=groups.get(key)
  if old is None or (bool(p['usable_units']),bool(p['matching_units']),p['storage_uri'].endswith('.md'))>(bool(old['usable_units']),bool(old['matching_units']),old['storage_uri'].endswith('.md')):groups[key]=p
 docs=list(groups.values());docs.sort(key=lambda p:release_version(p['storage_uri']),reverse=True)
 matched=[p for p in docs if p['matching_units']];unread=[p for p in docs if not p['usable_units']]
 # Read highest matching notes and later notes, not unrelated ancient releases.
 chosen=matched[:4]
 if matched:
  newest=release_version(matched[0]['storage_uri'])
  chosen+= [p for p in docs if release_version(p['storage_uri'])>newest and p not in chosen][:4]
 ids=[p['version_id'] for p in chosen]
 report={'requested':True,'keywords':terms,'release_path_scope':'Imported active /release_notes/ article bodies, all product families; compare only applicable product/version families.',
  'article_families_scanned':len(docs),'matching_article_families':len(matched),'families_without_usable_text':len(unread),'inventory_truncated':truncated,
  'complete':not truncated and not unread and not any(p['incomplete_extraction'] for p in docs),'method':'Case-insensitive keyword search over imported usable text, not proof that synonyms or unimported notes are absent. Source update dates are not deployment dates.',
  'matches':[dict(p,release_version='.'.join(map(str,release_version(p['storage_uri'])))) for p in matched[:40]],
  'later_notes':[dict(p,release_version='.'.join(map(str,release_version(p['storage_uri'])))) for p in docs if matched and release_version(p['storage_uri'])>release_version(matched[0]['storage_uri'])][:40],
  'missing_text_paths':[p['storage_uri'] for p in unread[:20]]}
 return ids,report

def collect(db,cfg,normalized,extra_queries=None,read_ids=None,prior=None):
 import knowledge_qa as qa
 profile=w.model_profile(db,cfg);spec,indexes=r.indexes(db,profile)
 if not any(x['relname']==spec['source_index'] and x['indisvalid'] for x in indexes):raise ValueError('Build-Search-Indexes.cmd must succeed before QA search')
 question=normalized['normalized_question'];terms=keywords(question,normalized.get('keywords',[]))
 queries=list(dict.fromkeys((extra_queries or normalized['search_queries'])+[question]))[:3]
 pool=[];diagnostics=[];review_candidates=[]
 # Focused original text keyword search is independent of semantic similarity and requires no new embeddings.
 base=r.base_sql('improved_hnsw',profile,True)
 if terms:
  pattern=keyword_pattern(terms)
  keyword_score=' + '.join("case when content_text ~* %s then 1 else 0 end" for _ in terms)
  lexical=w.q(db,f"""WITH b AS ({base}), matched AS (
    select b.*,({keyword_score}) keyword_score,
      regexp_replace(lower(storage_uri),'/article[.](md|json)$','/article') article_family
    from b where content_text ~* %s or title ~* %s), renditions AS (
    select matched.*,dense_rank() over(partition by article_family
      order by case when storage_uri like '%%/article.md' then 0 else 1 end,storage_uri) rendition
    from matched), chosen AS (select * from renditions where rendition=1), ranked AS (
    select chosen.*,row_number() over(partition by article_family order by keyword_score desc,id) family_rank from chosen)
    select * from ranked where family_rank<=3 order by keyword_score desc,article_family,id limit 201""",
    (None,None,*[keyword_pattern([term]) for term in terms],pattern,pattern)).fetchall()
  diagnostics.append({'kind':'FOCUSED_KEYWORDS','terms':terms,'returned':min(200,len(lexical)),'truncated':len(lexical)>200});pool.extend(lexical[:200])
 for query in queries:
  queryvec=w.vector(w.embed(cfg,query,True));db.commit()
  result=r.execute(db,profile,query,queryvec,'improved_hnsw',None,32,cfg.get('SearchCandidateBudget',100),True,True)
  diagnostics.append({'kind':'HYBRID_HNSW','query':query,'diagnostics':result['diagnostics']});pool.extend(result['passages']);pool.extend(result['neighbour_context'])
  # Reviews are a separate explicitly requested lane, never generic source answer stuffing.
  if normalized.get('include_reviews',False):
   findings,diag=r.derived_search(db,profile,queryvec,'improved_hnsw')
   review_packet=qa.evidence_packet({'derived_findings':findings[:3]})
   for p in review_packet:
    if len(p['text'])>10000:p['text']=p['text'][:10000];p['snapshot_truncated']=True
   review_candidates.extend(review_packet)
 # Priority order: original body matches then diverse semantic hits. No bank-specific answers/aliases are hardcoded.
 pool=diverse(rank_pool(pool,terms),32,3);read_versions_ids=[p['version_id'] for p in pool[:4]]
 report={'requested':False}
 if wants_chronology(normalized):
  release_ids,report=chronology(db,profile,terms);read_versions_ids=release_ids+read_versions_ids
 # Verifier can only ask to read versions already present in its evidence packet.
 permitted={str(p['version_id']) for p in (prior or []) if p['kind']=='SOURCE'}|{str(p['version_id']) for p in pool}
 requested=list(read_ids or [])
 if any(str(i) not in permitted for i in requested):raise ValueError('Verifier requested a source version outside the supplied evidence')
 surrounding,read_report=read_versions(db,profile,requested+read_versions_ids)
 new=qa.evidence_packet({'passages':enrich(db,pool+surrounding)})
 # Carry source metadata through the citation adapter.
 byid={str(p['id']):p for p in pool+surrounding}
 for p in new:
  row=byid[p['unit_id']]
  for key in ['release_version','note_last_updated','source_modified_at']:p[key]=row.get(key)
  p['storage_uri']=row.get('storage_uri');p['source_title']=row.get('title');p['source_metadata']=row.get('source_metadata',{})
 evidence=merge_evidence(prior or [],new,char_budget=100000 if prior else 70000)
 review_ids={p['record_id'] for p in evidence if p['kind']=='REVIEW'}
 remaining=max(0,3-len(review_ids))
 evidence=merge_evidence(evidence,[p for p in review_candidates if p['record_id'] not in review_ids][:remaining])
 supplied={p.get('unit_id') for p in evidence if p['kind']=='SOURCE'}
 for read in read_report:
  n=sum(str(p['id']) in supplied for p in surrounding if str(p['version_id'])==read['version_id'])
  read['units_supplied']=n;read['complete_usable_text']=read['complete_usable_text'] and n==read['usable_units_total']
 return {'evidence':evidence,'searches':diagnostics,'source_reads':read_report,'release_comparison':report,
  'coverage':'Bounded original-source investigation. Catalog files excluded from factual search. A complete usable-text read is not proof that images, blocked files or unimported content were examined. Inferences and proposed reviews remain labelled.'}

def diagnose(db,cfg,query):
 if not 2<=len(query.strip())<=100:raise ValueError('Diagnostic keyword must contain 2–100 characters')
 terms=keywords(query,[query]);profile=w.model_profile(db,cfg);base=r.base_sql('improved_hnsw',profile,True);pattern=keyword_pattern(terms)
 rows=w.q(db,f"""WITH b AS ({base}) select b.storage_uri,b.version_id,count(*) matching_units,
 count(e.content_unit_id) embedded_matching_units from b left join retrieval.content_embeddings e on e.content_unit_id=b.id and e.profile_id=%s
 where b.content_text ~* %s group by b.storage_uri,b.version_id order by b.storage_uri limit 101""",(None,None,profile['id'],pattern)).fetchall()
 result={'terms':terms,'matching_source_versions':rows[:100],'truncated':len(rows)>100,'note':'Direct keyword check of imported usable text and this profile vectors. Zero matches does not establish absence from original files or unimported/blocked sources.'}
 folder=w.BASE/'runtime/knowledge-diagnostics';folder.mkdir(parents=True,exist_ok=True);path=folder/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json');path.write_text(w.j(result),encoding='utf-8');result['report_json']=str(path);return result
