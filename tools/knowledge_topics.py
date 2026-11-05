"""POC 2 topic retrieval. Search normalization never rewrites original citation text."""
import re,hashlib
GENERIC={'setting','settings','permission','permissions','button','buttons','click','clicking','article','articles','documentation','document','required','requirement','requirements','explain','find','relevant','source','sources','td','tradedesk','how','what','where','which','the','a','an','to','for','of','in','and','or','do','does','i','after','before','please','cite','view'}
# 'view' is useful as part of an explicit phrase but weak alone.
def stem(word):
 if not re.fullmatch('[a-z]+',word):return word
 if len(word)>5 and word.endswith('ies'):return word[:-3]+'y'
 if len(word)>4 and word.endswith('s') and not word.endswith(('ss','us')):word=word[:-1]
 for suffix in ['ing','ed']:
  if len(word)>len(suffix)+3 and word.endswith(suffix):
   word=word[:-len(suffix)]
   if len(word)>2 and word[-1]==word[-2]:word=word[:-1]
   break
 return word

def tokens(text):return [stem(x) for x in re.findall(r'[a-z0-9_]+',text.casefold())]
def informative(term):return [x for x in re.findall(r'[a-z0-9_]+',term.casefold()) if x not in GENERIC and len(x)>1]
def search_terms(question,proposed,queries=None,revised=None):
 values=list(revised or [])
 if queries:
  for query in queries:
   values.extend(re.findall(r'"([^"\n]{2,100})"',query))
  if not values:
   values.extend(' '.join(informative(query)) for query in queries)
 if not values:values=list(proposed)
 clean=[]
 for term in values:
  term=' '.join(term.split())
  if 2<=len(term)<=100 and term.casefold() not in {t.casefold() for t in clean}:clean.append(term)
 focused=[t for t in clean if informative(t)]
 return (focused or clean or [' '.join(informative(question)) or question[:100]])[:8]

def topic_score(row,terms):
 body=tokens(row['content_text']);title=tokens(row.get('title',''));score=0.0
 for term in terms:
  words=tokens(term);main=[stem(x) for x in informative(term)]
  if not main:
   score+=.05*int(all(x in body for x in words));continue
  # Topic phrases, especially in titles, outrank generic setup/permission words.
  phrase=' '.join(words);body_text=' '.join(body);title_text=' '.join(title)
  score+=12*int(phrase in title_text)+5*int(phrase in body_text)
  score+=4*sum(x in title for x in main)+sum(x in body for x in main)
 return score+min(2.0,25*float(row.get('score',0)))

def distinct_sources(rows):
 ids=[];seen={};aliases=[];versions=set()
 for row in rows:
  version=str(row['version_id'])
  if version in versions:continue
  versions.add(version)
  signature=row.get('source_signature') or 'version:'+version
  # Signature is computed from ALL usable source units, not a matching snippet.
  key=(row.get('evidence_role','UNKNOWN'),signature)
  if key in seen:aliases.append({'version_id':version,'same_text_as_version':seen[key],'file':row.get('storage_uri'),'method':'identical complete usable-text signature'})
  else:seen[key]=version;ids.append(version)
 return ids,aliases

def annotate_signatures(db,profile,rows):
 import worker as w,retrieval_v017 as r
 ids=list(dict.fromkeys(str(p['version_id']) for p in rows))
 if not ids:return rows
 base=r.base_sql('improved_hnsw',profile,True)
 meta=w.q(db,f"""WITH b AS ({base}) select version_id,md5(string_agg(content_sha256,',' order by coalesce(start_seconds,0),case when unit_key ~ '^[0-9]+$' then unit_key::numeric else 0 end,unit_key,id)) signature
 from b where version_id=any(%s::uuid[]) group by version_id""",(None,None,ids)).fetchall()
 signatures={str(p['version_id']):p['signature'] for p in meta}
 for p in rows:p['source_signature']=signatures.get(str(p['version_id']))
 return rows

def lexical(db,profile,terms):
 import worker as w,retrieval_v017 as r
 base=r.base_sql('improved_hnsw',profile,True)
 terms=search_terms('',terms)
 # PostgreSQL English search supplies stemming (posted/posting), not guessed synonyms.
 predicates=[];scores=[];args=[]
 for term in terms:
  predicates.append("(to_tsvector('english',title) @@ plainto_tsquery('english',%s) or to_tsvector('english',content_text) @@ plainto_tsquery('english',%s))")
  scores.append("(12*case when to_tsvector('english',title) @@ plainto_tsquery('english',%s) then 1 else 0 end+4*case when to_tsvector('english',content_text) @@ plainto_tsquery('english',%s) then 1 else 0 end)")
  args.extend([term,term])
 rows=w.q(db,f"""WITH b AS ({base}), signatures AS (
 select version_id,evidence_role,min(storage_uri) storage_uri,md5(string_agg(content_sha256,',' order by coalesce(start_seconds,0),case when unit_key ~ '^[0-9]+$' then unit_key::numeric else 0 end,unit_key,id)) signature
 from b group by version_id,evidence_role), matched AS (
 select b.*,({' + '.join(scores)}) topic_score,regexp_replace(lower(b.storage_uri),'/article[.](md|json)$','/article') article_family from b
 where {' or '.join(predicates)}), source_scores AS (
 select version_id,max(topic_score) best_score from matched group by version_id), representatives AS (
 select signatures.*,row_number() over(partition by evidence_role,signature order by best_score desc,storage_uri,version_id) copy_rank
 from signatures join source_scores using(version_id)), ranked AS (
 select matched.*,row_number() over(partition by article_family order by topic_score desc,case when storage_uri like '%%/article.md' then 0 else 1 end,id) source_rank from matched join (select version_id from representatives where copy_rank=1) rp using(version_id))
 select * from ranked where source_rank<=3 order by topic_score desc,article_family,id limit 201""",(None,None,*args,*args)).fetchall()
 return rows[:200],{'kind':'FOCUSED_TOPICS','terms':terms,'returned':min(200,len(rows)),'truncated':len(rows)>200,'method':'English full-text topic/title search; original literal text retained'}
