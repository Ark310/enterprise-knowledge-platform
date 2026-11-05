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

def merge_evidence(old,new,char_budget=100000,max_items=80,reserved_ids=()):
 out=[dict(p) for p in old];seen={(p['kind'],str(p.get('unit_id',p.get('record_id',p.get('frame_id'))))) for p in out};used=sum(len(p['text']) for p in out)
 counter=max([int(i[1:]) for i in list(reserved_ids)+[p.get('evidence_id','') for p in out] if i[1:].isdigit()]+[0])
 for p in new:
  key=(p['kind'],str(p.get('unit_id',p.get('record_id',p.get('frame_id')))))
  if key in seen:continue
  if len(out)>=max_items or used+len(p['text'])>char_budget:continue
  counter+=1
  p=dict(p,evidence_id=({'SOURCE':'S','REVIEW':'R','FRAME':'F'}[p['kind']])+str(counter));out.append(p);seen.add(key);used+=len(p['text'])
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

def read_versions(db,profile,version_ids,per_version=24,terms=None):
 base=r.base_sql('improved_hnsw',profile,True);out=[];reports=[]
 terms=terms or [];pattern=keyword_pattern(terms)
 for version_id in list(dict.fromkeys(str(uuid.UUID(str(x))) for x in version_ids))[:8]:
  total=w.one(db,f'WITH b AS ({base}) select count(*) n from b where version_id=%s',(None,None,version_id))['n']
  # Choose question hits + neighbouring units and both ends, rather than a source prefix.
  score=' + '.join("case when content_text ~* %s then 1 else 0 end" for _ in terms) or '0'
  rows=w.q(db,f"""WITH b AS ({base}), ordered AS (
   select b.*,row_number() over(order by coalesce(start_seconds,0),case when unit_key ~ '^[0-9]+$' then unit_key::numeric else 0 end,unit_key,id) rn,
   count(*) over() total,({score}) focus_score from b where version_id=%s), hits AS (
   select rn from ordered where focus_score>0 order by focus_score desc,rn limit 8), chosen AS (
   select o.* from ordered o where total<=%s or rn<=2 or rn>total-4
   or exists(select 1 from hits h where abs(h.rn-o.rn)<=1))
   select * from chosen order by case when total<=%s then 0 when rn>total-4 then 1 when focus_score>0 then 2 when rn<=2 then 3 else 4 end,
   focus_score desc,rn limit %s""",(None,None,*[keyword_pattern([t]) for t in terms],version_id,per_version,per_version,per_version)).fetchall()
  out.extend(rows);reports.append({'version_id':version_id,'usable_units_total':total,'units_read':len(rows),
   'selection':'Question keyword hits, neighbouring context, opening and ending; whole short source when within limit.',
   'complete_usable_text':bool(total) and total==len(rows)})
 return out,reports

def chronology(db,profile,terms,scope='any'):
 import knowledge_scope as ks
 if not terms:return [],{'requested':True,'complete':False,'reason':'No focused topic keywords; cannot establish a latest matching release.','required_matches':[]}
 base=r.base_sql('improved_hnsw',profile,True);pattern=keyword_pattern(terms)
 counts=','.join(f"count(b.id) filter(where b.content_text ~* %s) term_{i}" for i in range(len(terms)))
 rows=w.q(db,f"""WITH b AS ({base}) select v.id version_id,v.storage_uri,s.title,v.source_modified_at,
  count(b.id) usable_units,count(b.id) filter(where b.content_text ~* %s) matching_units,{counts},
  exists(select 1 from knowledge.extractions ex where ex.source_version_id=v.id and ex.is_active and ex.status<>'COMPLETE') incomplete_extraction
  from knowledge.source_versions v join knowledge.sources s on s.id=v.source_id left join b on b.version_id=v.id
  where v.lifecycle_status='ACTIVE' and lower(v.storage_uri) like '%%/release_notes/%%'
  and lower(v.storage_uri) ~ '/article[.](md|json)$'
  group by v.id,s.title order by v.storage_uri,v.id limit 1001""",(None,None,pattern,*[keyword_pattern([t]) for t in terms])).fetchall()
 truncated=len(rows)>1000;rows=rows[:1000];groups={}
 for p in rows:
  if scope!='any' and ks.product_family(p['storage_uri'])!=scope:continue
  p['term_counts']={t:p.pop('term_'+str(i)) for i,t in enumerate(terms)}
  key=family(p['storage_uri']);old=groups.get(key)
  quality=lambda d:(sum(bool(v) for v in d['term_counts'].values()),bool(d['usable_units']),d['storage_uri'].endswith('.md'))
  if old is None or quality(p)>quality(old):groups[key]=p
 docs=list(groups.values());docs.sort(key=lambda p:release_version(p['storage_uri']),reverse=True)
 matched=[p for p in docs if p['matching_units']];unread=[p for p in docs if not p['usable_units']]
 ids,required=ks.choose_releases(docs,terms,scope)
 report={'requested':True,'keywords':terms,'product_scope':scope,'required_matches':required,
  'release_path_scope':'Imported active release-note article bodies; comparison and reading slots separated by product family.',
  'article_families_scanned':len(docs),'matching_article_families':len(matched),'families_without_usable_text':len(unread),'inventory_truncated':truncated,
  'complete':not truncated and not unread and not any(p['incomplete_extraction'] for p in docs),
  'method':'Independent keyword counts per exact phrase/component. Latest matching passage per term/product is required; bounded keyword scan is not proof of synonym or original-file absence. Update dates are not deployment dates.',
  'matches':[dict(p,release_version='.'.join(map(str,release_version(p['storage_uri'])))) for p in matched[:40]],
  'later_notes':[dict(p,release_version='.'.join(map(str,release_version(p['storage_uri'])))) for p in docs if matched and release_version(p['storage_uri'])>release_version(matched[0]['storage_uri'])][:40],
  'missing_text_paths':[p['storage_uri'] for p in unread[:20]]}
 return ids,report

def release_anchors(db,profile,requirements):
 base=r.base_sql('improved_hnsw',profile,True);out=[]
 for a in requirements:
  rows=w.q(db,f"WITH b AS ({base}) select * from b where version_id=%s and content_text ~* %s order by unit_key,id limit 3",
   (None,None,a['version_id'],keyword_pattern([a['term']]))).fetchall()
  out.extend(rows)
 return out

def collect(db,cfg,normalized,extra_queries=None,read_ids=None,prior=None):
 import knowledge_qa as qa
 import knowledge_scope as ks
 profile=w.model_profile(db,cfg);spec,indexes=r.indexes(db,profile)
 if not any(x['relname']==spec['source_index'] and x['indisvalid'] for x in indexes):raise ValueError('Build-Search-Indexes.cmd must succeed before QA search')
 question=normalized['normalized_question'];terms=keywords(question,normalized.get('keywords',[]))
 bundle=ks.resolve_bundle(db,cfg,normalized)
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
 if wants_chronology(normalized):
  fam=ks.requested_family(normalized)
  pool=[p for p in pool if '/release_notes/' in urllib.parse.unquote(p.get('storage_uri','')).lower() and (fam=='any' or ks.product_family(p['storage_uri'])==fam)]
 pool=diverse(rank_pool(pool,terms),32,3)
 # Choose DISTINCT sources before the limit, not four chunks from one source.
 read_versions_ids=list(dict.fromkeys(str(p['version_id']) for p in pool))[:4]
 report={'requested':False,'required_matches':[]}
 if wants_chronology(normalized):
  release_ids,report=chronology(db,profile,terms,ks.requested_family(normalized));read_versions_ids=release_ids+read_versions_ids
 # Verifier can only ask to read versions already present in its evidence packet.
 permitted={str(p['version_id']) for p in (prior or []) if p['kind']=='SOURCE'}|{str(p['version_id']) for p in pool}
 requested=list(read_ids or [])
 if any(str(i) not in permitted for i in requested):raise ValueError('Verifier requested a source version outside the supplied evidence')
 # Companion reads are independent of vector rank. Each named recording gets its own read allowance.
 companions,companion_report=read_versions(db,profile,bundle['required_version_ids'],terms=terms)
 anchors=release_anchors(db,profile,report.get('required_matches',[]))
 surrounding,read_report=read_versions(db,profile,requested+read_versions_ids,terms=terms)
 read_report=companion_report+read_report
 required_rows=companions+anchors
 all_rows=required_rows+surrounding+pool
 new=qa.evidence_packet({'passages':enrich(db,all_rows)})
 # Carry source metadata through the citation adapter.
 byid={str(p['id']):p for p in all_rows}
 for p in new:
  row=byid[p['unit_id']]
  for key in ['release_version','note_last_updated','source_modified_at']:p[key]=row.get(key)
  p['storage_uri']=row.get('storage_uri');p['source_title']=row.get('title');p['source_metadata']=row.get('source_metadata',{})
 required_ids={str(p['id']) for p in required_rows}
 evidence=ks.assemble(prior or [],[p for p in new if p['unit_id'] in required_ids],[p for p in new if p['unit_id'] not in required_ids],char_budget=100000 if prior else 70000)
 review_ids={p['record_id'] for p in evidence if p['kind']=='REVIEW'}
 remaining=max(0,3-len(review_ids))
 evidence=merge_evidence(evidence,[p for p in review_candidates if p['record_id'] not in review_ids][:remaining],reserved_ids=[p['evidence_id'] for p in (prior or [])])
 supplied={p.get('unit_id') for p in evidence if p['kind']=='SOURCE'}
 for read in read_report:
  n=sum(str(p['id']) in supplied for p in {str(x['id']):x for x in all_rows}.values() if str(p['version_id'])==read['version_id'])
  read['units_supplied']=n;read['complete_usable_text']=read['complete_usable_text'] and n==read['usable_units_total']
 import knowledge_visual
 visual,visual_report=knowledge_visual.prepare(db,cfg,normalized,companions+surrounding+pool)
 evidence=merge_evidence(evidence,visual,char_budget=110000,max_items=110,reserved_ids=[p['evidence_id'] for p in (prior or [])])
 scope=ks.completeness(bundle,report.get('required_matches',[]),evidence,visual_report)
 return {'scope':scope,'evidence':evidence,'visual_inspection':visual_report,'searches':diagnostics,'source_reads':read_report,'release_comparison':report,
  'coverage':'Bounded original-source investigation. Catalog files excluded from factual search. A complete usable-text read is not proof that images, blocked files or unimported content were examined. Inferences and proposed reviews remain labelled.'}

def diagnose(db,cfg,query):
 if not 2<=len(query.strip())<=100:raise ValueError('Diagnostic keyword must contain 2–100 characters')
 terms=keywords(query,[query]);profile=w.model_profile(db,cfg);base=r.base_sql('improved_hnsw',profile,True);pattern=keyword_pattern(terms)
 rows=w.q(db,f"""WITH b AS ({base}) select b.storage_uri,b.version_id,count(*) matching_units,
 count(e.content_unit_id) embedded_matching_units from b left join retrieval.content_embeddings e on e.content_unit_id=b.id and e.profile_id=%s
 where b.content_text ~* %s group by b.storage_uri,b.version_id order by b.storage_uri limit 101""",(None,None,profile['id'],pattern)).fetchall()
 result={'terms':terms,'matching_source_versions':rows[:100],'truncated':len(rows)>100,'note':'Direct keyword check of imported usable text and this profile vectors. Zero matches does not establish absence from original files or unimported/blocked sources.'}
 folder=w.BASE/'runtime/knowledge-diagnostics';folder.mkdir(parents=True,exist_ok=True);path=folder/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json');path.write_text(w.j(result),encoding='utf-8');result['report_json']=str(path);return result
