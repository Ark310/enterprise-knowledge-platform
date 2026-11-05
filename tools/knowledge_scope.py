"""POC 2 source identity, required evidence and product-aware release selection."""
import re,urllib.parse
from pathlib import Path
import worker as w

def decoded(uri):return urllib.parse.unquote(uri).replace('\\','/').casefold()
def companion(video,transcript):
 video=decoded(video);transcript=decoded(transcript)
 if video.rsplit('/',1)[0]!=transcript.rsplit('/',1)[0]:return False
 stem=video.rsplit('/',1)[-1].rsplit('.',1)[0]
 name=transcript.rsplit('/',1)[-1]
 if name.endswith(('.srt','.vtt')):return name.rsplit('.',1)[0]==stem
 return name.endswith('.docx') and name[:-5] in {stem+'_transcript',stem+' transcript',stem+'-transcript'}

def resolve_bundle(db,cfg,normalized):
 from knowledge_visual import recording_matches
 names=normalized.get('recording_names',[])
 result={'recordings':[],'required_version_ids':[],'blocking_errors':[],'clarification':None}
 if not names:return result
 videos=w.q(db,"select id,source_id,storage_uri,content_sha256 from knowledge.source_versions where lifecycle_status='ACTIVE' and lower(storage_uri) ~ '[.](mp4|mkv|mov|wmv|avi|webm)$'").fetchall()
 for name in names:
  matches=recording_matches(videos,name,Path(cfg['DataRoot']));item={'requested_name':name,'matches':len(matches),'transcripts':[]};result['recordings'].append(item)
  if len(matches)!=1:
   result['blocking_errors'].append('Named recording missing or ambiguous: '+name)
   if len(matches)>1:result['clarification']='More than one recording matches '+name+'. Please provide its relative path under the data folder.'
   continue
  rec=matches[0];item.update(version_id=str(rec['id']),file=rec['storage_uri'])
  candidates=w.q(db,"""select v.id,v.storage_uri,v.content_sha256,
    exists(select 1 from knowledge.source_links l where l.from_version_id=v.id and l.to_source_id=%s
      and l.relationship='TRANSCRIPT_FOR' and l.resolution_status='RESOLVED'
      and (l.to_version_id is null or l.to_version_id=%s)) linked
    from knowledge.source_versions v where v.lifecycle_status='ACTIVE'
    and lower(v.storage_uri) ~ '[.](srt|vtt|docx)$'""",(rec['source_id'],rec['id'])).fetchall()
  found=[v for v in candidates if v['linked'] or companion(rec['storage_uri'],v['storage_uri'])]
  found.sort(key=lambda v:(not v['linked'],not v['storage_uri'].lower().endswith(('.srt','.vtt')),v['storage_uri']))
  for v in found:
   item['transcripts'].append({'version_id':str(v['id']),'file':v['storage_uri'],'pairing':'REGISTERED_LINK' if v['linked'] else 'SAME_FOLDER_EXACT_FILENAME','content_sha256':v['content_sha256']})
   result['required_version_ids'].append(str(v['id']))
  if not found:result['blocking_errors'].append('No imported companion transcript for '+name)
 result['required_version_ids']=list(dict.fromkeys(result['required_version_ids']))
 return result

def product_family(uri):
 path=decoded(uri)
 for part in ['tradedesk','web4','web2','api','formflow','saleshub']:
  if '/'+part+'/' in path:return part
 return 'other'

def requested_family(normalized):
 q=normalized['normalized_question'].casefold()
 if re.search(r'\bform\s*flow\b',q):return 'formflow'
 if re.search(r'\bsales\s*hub\b',q):return 'saleshub'
 if re.search(r'\b(rest\s*api|web\s*api|api)\b',q):return 'api'
 if re.search(r'\bweb\s*4\b',q):return 'web4'
 if re.search(r'\bweb\s*2\b',q):return 'web2'
 if re.search(r'\b(td|tradedesk)\b',q) and not re.search(r'\bweb\b',q):return 'tradedesk'
 return 'any'

def choose_releases(docs,terms,scope):
 from knowledge_search import release_version
 docs=[p for p in docs if scope=='any' or product_family(p['storage_uri'])==scope]
 docs=sorted(docs,key=lambda p:release_version(p['storage_uri']),reverse=True)
 selected=[];required=[]
 # Each exact phrase and component gets its own newest match, within its product family.
 for fam in sorted({product_family(p['storage_uri']) for p in docs}):
  group=[p for p in docs if product_family(p['storage_uri'])==fam]
  for term in terms:
   match=next((p for p in group if p.get('term_counts',{}).get(term,0)),None)
   if match:
    required.append({'term':term,'version_id':str(match['version_id']),'file':match['storage_uri'],'product_family':fam})
    if str(match['version_id']) not in selected:selected.append(str(match['version_id']))
 # Required exact-name anchors precede optional higher notes and broader matching context.
 for p in docs:
  if len(selected)>=8:break
  if str(p['version_id']) not in selected:selected.append(str(p['version_id']))
 return selected[:8],required

def assemble(prior,required,optional,char_budget=70000,max_items=80,prefer_new=False):
 def key(p):return (p['kind'],str(p.get('unit_id',p.get('record_id',p.get('frame_id')))))
 known={key(p):dict(p) for p in prior}
 counter=max([int(p['evidence_id'][1:]) for p in prior if p.get('evidence_id','')[1:].isdigit()]+[0])
 groups={}
 for p in required:groups.setdefault(str(p.get('version_id',p.get('unit_id'))),[]).append(p)
 ordered=[]
 while any(groups.values()):
  for rows in groups.values():
   if rows:ordered.append(rows.pop(0))
 out=[];seen=set();used=0
 # Mandatory rows first, then retained old optional rows, then new optional rows.
 for p in ordered+(list(optional)+list(prior) if prefer_new else list(prior)+list(optional)):
  k=key(p)
  if k in seen:continue
  if len(out)>=max_items or used+len(p['text'])>char_budget:continue
  if k in known:p=dict(known[k])
  else:
   counter+=1;p=dict(p,evidence_id={'SOURCE':'S','FRAME':'F','REVIEW':'R'}[p['kind']]+str(counter))
  out.append(p);seen.add(k);used+=len(p['text'])
 return out

def completeness(bundle,anchors,evidence,visual):
 errors=list(bundle['blocking_errors']);sources=[p for p in evidence if p['kind']=='SOURCE']
 present={str(p['version_id']) for p in sources}
 for recording in bundle['recordings']:
  for t in recording['transcripts']:
   if t['version_id'] not in present:errors.append('Required companion transcript not supplied: '+t['file'])
 for a in anchors:
  if not any(str(p['version_id'])==a['version_id'] and a['term'].casefold() in p['text'].casefold() for p in sources):
   errors.append('Required release match passage not supplied: '+a['term']+' in '+a['file'])
 if visual.get('requested'):
  if not visual.get('recordings'):errors.append('No recording identified for required visual inspection')
  for rec in visual.get('recordings',[]):
   if rec.get('status')!='SAMPLED' or not any(p['kind']=='FRAME' and str(p.get('version_id'))==str(rec.get('source_version_id')) for p in evidence):errors.append('Required recording images unavailable: '+rec.get('requested_name',''))
 return {'blocking_errors':list(dict.fromkeys(errors)),'required_transcript_versions':bundle['required_version_ids'],
  'required_release_matches':anchors,'recordings':bundle['recordings'],'clarification':bundle.get('clarification'),
  'note':'Host checks source presence; the independent Verifier must still check relevance, contradictions and answer completeness. Pairing is not independent audio/transcript alignment.'}
