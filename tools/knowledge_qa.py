"""Dataset retrieval audit and deterministic gates. Chat history never enters vector indexes."""
import json,re,uuid
from pathlib import Path
import jsonschema
import worker as w

CONTRACT=w.BASE/'contracts/knowledge-qa.schema.json'
def schema_errors(obj,part):
 schema=json.loads(CONTRACT.read_text(encoding='utf-8'))
 return [e.message for e in jsonschema.Draft202012Validator(schema['$defs'][part]).iter_errors(obj)]

def protected_tokens(text):
 # Numbers/versions/ticket IDs, quoted source names and uppercase product acronyms cannot be guessed away.
 return set(re.findall(r'\b\d+(?:[.:-]\d+)*\b|\b[A-Z][A-Z0-9_]{1,}\b|"[^"\n]+"',text))

def canonical_normalization(original,obj,recordings=None):
 # Backward-compatible v024 visual_check meant video only. Keep product/identifier text unchanged.
 from copy import deepcopy
 n=deepcopy(obj)
 if schema_errors(n,'normalization'):return n
 names=list(recordings) if recordings else n.get('recording_names',[])
 targets=list(n.get('visual_targets',[]));text=original+' '+n['normalized_question']
 transcript_only=bool(re.search(r'\b(transcript[- ]only|transcript only|only (?:the )?transcript|no (?:frames|images)|without (?:frames|images))\b',text,re.I))
 if names and not transcript_only:targets.append('VIDEO_FRAME')
 if not targets and n.get('visual_check'):
  targets.append('VIDEO_FRAME' if re.search(r'\b(video|recording|walkthrough|vlcs?)\b',text,re.I) and not re.search(r'\b(article|documentation) (?:screenshots?|images?)\b',text,re.I) else 'ARTICLE_IMAGE')
 if not targets and re.search(r'\b(screenshot|picture|image)s?\b',text,re.I):targets.append('ARTICLE_IMAGE')
 if transcript_only:targets=[t for t in targets if t!='VIDEO_FRAME']
 n['visual_targets']=list(dict.fromkeys(targets));n['visual_check']='VIDEO_FRAME' in targets;n['recording_names']=names
 return n

def validate_normalization(original,obj):
 errors=schema_errors(obj,'normalization')
 if errors:return errors
 # Current broad quantities cannot silently inherit a precise older count.
 if re.search(r'\b(multiple|several|various)\b',original,re.I) and not obj['needs_clarification']:
  quantity=r'\b(?:[0-9]+|one|two|three|four|five|six|seven|eight|nine|ten)\b'
  introduced=set(re.findall(quantity,obj['normalized_question'].lower()))-set(re.findall(quantity,original.lower()))
  if introduced:errors.append('Broad quantity narrowed to an unconfirmed count; ask for clarification')
 if obj['visual_check'] and not obj['recording_names'] and not obj['needs_clarification']:errors.append('Visual investigation needs a recording name or clarification')
 missing=protected_tokens(original)-protected_tokens(obj['normalized_question'])
 if missing:errors.append('Normalization changed protected identifiers or quoted titles: '+', '.join(sorted(missing)))
 if obj['needs_clarification'] and not obj['clarification_question'].strip():errors.append('Clarification question is required')
 return errors

def evidence_packet(data):
 result=[];seen=set()
 for p in data.get('passages',[]):
  key=str(p['id'])
  if key in seen:continue
  seen.add(key)
  result.append({'evidence_id':'S'+str(len(result)+1),'kind':'SOURCE','unit_id':key,'version_id':str(p['version_id']),
   'file':p.get('locator',{}).get('file',p.get('title','Unknown')),'text':p['content_text'],'locator':p.get('locator',{}),
   'evidence_role':p.get('evidence_role','UNKNOWN')})
 for p in data.get('derived_findings',[]):
  if p.get('evidence_superseded') or p.get('review_status')=='REJECTED':continue
  key='review:'+str(p['id'])
  if key in seen:continue
  seen.add(key)
  result.append({'evidence_id':'R'+str(len(result)+1),'kind':'REVIEW','record_id':str(p['id']),
   'run_id':str(p.get('run_id','')),'file':'Saved review '+str(p.get('record_key',p['id'])),
   'text':p['statement']+'\n'+json.dumps(p.get('details',{}),ensure_ascii=False,default=str),
   'review_status':p.get('review_status','AGENT_PROPOSED'),'locator':{'record_key':p.get('record_key')}})
 return result

def validate_answer(obj,evidence):
 errors=schema_errors(obj,'answer')
 if errors:return errors
 refs={p['evidence_id']:p for p in evidence};seen=set()
 if obj['status'] in ('ANSWER','PARTIAL') and not obj['claims']:errors.append('ANSWER requires supported claims')
 if obj['status'] not in ('ANSWER','PARTIAL') and obj['claims']:errors.append('Non-answer cannot contain factual claims')
 if obj['status']=='ANSWER' and obj.get('unresolved'):errors.append('Unresolved requested details require PARTIAL status')
 if obj['status']=='PARTIAL':
  if not obj.get('unresolved'):errors.append('PARTIAL requires explicit unresolved details')
  if 'procedure_complete' not in obj:errors.append('PARTIAL requires procedure_complete')
 if obj['status']=='CLARIFY' and not obj['clarification_question'].strip():errors.append('Missing clarification question')
 for claim in obj['claims']:
  if claim['id'] in seen:errors.append('Duplicate claim ID')
  seen.add(claim['id']);source=False
  for cite in claim['citations']:
   p=refs.get(cite['evidence_id'])
   if p is None:errors.append('Unknown evidence ID '+cite['evidence_id']);continue
   if not cite['excerpt'].strip() or cite['excerpt'] not in p['text']:errors.append('Citation excerpt is not literal evidence')
   source|=p['kind']=='SOURCE'
  if not claim['citations']:errors.append('Every claim needs evidence')
  if claim['basis']=='VISUAL' and not any(refs.get(c['evidence_id'],{}).get('kind') in ('FRAME','USER_IMAGE','SOURCE_IMAGE') for c in claim['citations']):errors.append('Visual claim needs attached frame evidence')
  if claim['basis'] in ('SOURCE','INFERENCE') and not source:errors.append('Product facts/inferences need original source evidence, not just saved AI findings')
  if claim['basis']=='REVIEW_REPORT' and not any(refs.get(c['evidence_id'],{}).get('kind')=='REVIEW' for c in claim['citations']):errors.append('Review report must cite a saved review')
 for ident in obj.get('illustrations',[]):
  if refs.get(ident,{}).get('kind') not in ('FRAME','SOURCE_IMAGE'):errors.append('Illustration must be a supplied original source image')
 return errors

def validate_verdict(obj,answer,retrieval=None):
 errors=schema_errors(obj,'verdict')
 if errors:return errors
 ids=[c['id'] for c in answer.get('claims',[])];checked=[c['claim_id'] for c in obj['claim_checks']]
 if sorted(ids)!=sorted(checked):errors.append('Verifier must check every claim exactly once')
 if obj['decision'] in ('PASS','PARTIAL_PASS'):
  partial=obj['decision']=='PARTIAL_PASS'
  if partial and answer.get('status')!='PARTIAL':errors.append('PARTIAL_PASS requires PARTIAL answer')
  if partial and obj['requested_scope_complete']:errors.append('Partial approval cannot claim complete requested scope')
  if partial and (not answer.get('unresolved') or not answer.get('claims') or 'procedure_complete' not in answer):errors.append('Partial approval needs supported claims, unresolved items and procedure completeness')
  if not partial and not obj['requested_scope_complete']:errors.append('PASS requires the requested scope to be complete')
  if (retrieval or {}).get('scope',{}).get('blocking_errors'):errors.append('PASS blocked by missing required source evidence')
  if not obj['evidence_coverage_sufficient']:errors.append('PASS requires sufficient evidence coverage')
  if obj.get('retrieval_queries') or obj.get('read_source_versions') or obj.get('retrieval_keywords'):errors.append('PASS cannot have outstanding evidence requests')
  if not all(obj[k] for k in ['addresses_question','normalization_faithful','premise_supported','human_readable']):errors.append('PASS requires all answer checks')
  selected=answer.get('illustrations',[]);checked_images=obj.get('illustration_checks',[])
  if sorted(selected)!=sorted(x['evidence_id'] for x in checked_images):errors.append('Every selected illustration needs an independent relevance check')
  if not all(x['relevant'] for x in checked_images):errors.append('Unrelated illustration cannot be published')
  if not all(c['supported'] for c in obj['claim_checks']):errors.append('PASS contains unsupported claims')
  if not partial and answer.get('status')!='ANSWER':errors.append('Cannot pass a non-answer')
 return errors

def may_investigate(verdict,retrieval):
 return not schema_errors(verdict,'verdict') and bool((retrieval or {}).get('scope',{}).get('blocking_errors'))

def ensure(db):
 if not w.one(db,"select exists(select 1 from pg_constraint where conrelid='knowledge_qa.turns'::regclass and conname='qa_turns_publication_v023') t")['t']:raise ValueError('Run Setup-POC.cmd for the v0.23 verified-partial migration. Existing sources and vectors are preserved.')
 if not w.one(db,"select exists(select 1 from information_schema.columns where table_schema='knowledge_qa' and table_name='evidence' and column_name='frame_id') t")['t']:raise ValueError('Run Initialize-Database.cmd or Setup-POC.cmd for the additive v0.20 migration first.')

def begin(db,args):
 ensure(db);sid=str(uuid.UUID(args['session_id']));tid=str(uuid.UUID(args['turn_id']));question=args['question'].strip()
 if not question or len(question)>12000:raise ValueError('Question must contain 1–12000 characters')
 w.q(db,'insert into knowledge_qa.sessions(id) values(%s) on conflict do nothing',(sid,))
 w.q(db,"insert into knowledge_qa.turns(id,session_id,question,status) values(%s,%s,%s,'PROCESSING')",(tid,sid,question))
 db.commit();return {'turn_id':tid}

def event(db,args):
 ensure(db);tid=str(uuid.UUID(args['turn_id']));stage=args['stage']
 if stage not in {'NORMALIZATION','DRAFT','VERIFICATION','VALIDATION','FAILURE'}:raise ValueError('Unknown QA stage')
 row=w.one(db,'select status,question from knowledge_qa.turns where id=%s',(tid,))
 if not row or row['status']!='PROCESSING':raise ValueError('QA turn is not processing')
 w.q(db,'insert into knowledge_qa.events(turn_id,stage,payload) values(%s,%s,%s::jsonb)',(tid,stage,w.j(args['payload'])))
 if stage=='NORMALIZATION' and not validate_normalization(row['question'],args['payload']):
  w.q(db,'update knowledge_qa.turns set normalization=%s::jsonb where id=%s',(w.j(args['payload']),tid))
 db.commit();return {'saved':True}

def retrieve(db,cfg,args):
 ensure(db);tid=str(uuid.UUID(args['turn_id']));row=w.one(db,'select question,status from knowledge_qa.turns where id=%s',(tid,))
 if not row or row['status']!='PROCESSING':raise ValueError('Unknown/inactive retrieval turn')
 normalized=canonical_normalization(row['question'],args['normalization']);errors=validate_normalization(row['question'],normalized)
 if errors:raise ValueError('; '.join(errors))
 if normalized['needs_clarification']:raise ValueError('Clarification required before searching')
 import knowledge_search
 previous=[p['snapshot'] for p in w.q(db,'select snapshot from knowledge_qa.evidence where turn_id=%s order by evidence_key',(tid,)).fetchall()]
 expanding=bool(args.get('expand',False))
 if expanding:
  if (row:=w.one(db,'select retrieval from knowledge_qa.turns where id=%s',(tid,)))['retrieval'].get('expanded',False):raise ValueError('Only one bounded retrieval expansion is allowed')
  if len(args.get('queries',[]))>2 or any(not isinstance(x,str) or not 1<=len(x)<=2000 for x in args.get('queries',[])):raise ValueError('Invalid expansion queries')
  if len(args.get('keywords',[]))>8 or any(not isinstance(x,str) or not 2<=len(x)<=100 for x in args.get('keywords',[])):raise ValueError('Invalid revised keywords')
  if len(args.get('read_source_versions',[]))>4:raise ValueError('Too many requested source versions')
 result=knowledge_search.collect(db,cfg,normalized,args.get('queries') if expanding else None,args.get('read_source_versions') if expanding else None,previous,args.get('keywords') if expanding else None)
 import knowledge_visual
 if any(p['kind']=='FRAME' for p in result['evidence']):result['evidence']=knowledge_visual.stage_images(result['evidence'],args['work'])
 if args.get('web_images'):
  import chat_images
  result=chat_images.enrich(db,cfg,tid,result)
 for p in result['evidence']:
  if p['kind'] in ('USER_IMAGE','SOURCE_IMAGE'):continue
  w.q(db,"""insert into knowledge_qa.evidence(turn_id,evidence_key,content_unit_id,source_version_id,record_id,frame_id,snapshot)
    values(%s,%s,%s,%s,%s,%s,%s::jsonb) on conflict(turn_id,evidence_key) do nothing""",(tid,p['evidence_id'],p.get('unit_id'),p.get('version_id'),p.get('record_id'),p.get('frame_id'),w.j(p)))
 history=w.one(db,'select retrieval from knowledge_qa.turns where id=%s',(tid,))['retrieval'] or {}
 history['rounds']=history.get('rounds',[])+[{k:v for k,v in result.items() if k!='evidence'}];history['expanded']=expanding or history.get('expanded',False)
 w.q(db,'update knowledge_qa.turns set normalization=%s::jsonb,retrieval=%s::jsonb where id=%s',(w.j(normalized),w.j(history),tid));db.commit();return result

def finish(db,args):
 ensure(db);tid=str(uuid.UUID(args['turn_id']));row=w.one(db,'select * from knowledge_qa.turns where id=%s for update',(tid,))
 if not row or row['status']!='PROCESSING':raise ValueError('QA turn already finished or missing')
 status=args['status']
 if status not in {'VERIFIED','INSUFFICIENT_EVIDENCE','CLARIFY','FAILED','CANCELLED'}:raise ValueError('Invalid QA completion status')
 answer=args.get('answer');verdict=args.get('verdict');evidence=[r['snapshot'] for r in w.q(db,'select snapshot from knowledge_qa.evidence where turn_id=%s order by evidence_key',(tid,)).fetchall()]
 if status=='VERIFIED':
  errors=validate_answer(answer,evidence)+validate_verdict(verdict,answer,((row.get('retrieval') or {}).get('rounds') or [{}])[-1])
  if verdict.get('decision') not in ('PASS','PARTIAL_PASS'):errors.append('Verifier did not pass')
  # Recheck image bytes and original recording revision immediately before publication.
  for p in evidence:
   if p['kind'] in ('USER_IMAGE','SOURCE_IMAGE'):
    try:
     if w.file_hash(p['path'])!=p['image_sha256']:errors.append('Image attachment changed during this turn')
    except OSError:errors.append('Image attachment unavailable at publication')
   if p['kind']=='FRAME':
    try:
     if w.file_hash(p['path'])!=p['image_sha256']:errors.append('Frame evidence changed during this turn')
     import urllib.parse
     raw=urllib.parse.unquote(urllib.parse.urlparse(p['recording_uri']).path)
     if re.match(r'^/[A-Za-z]:/',raw):raw=raw[1:]
     if w.file_hash(raw)!=p['recording_sha256']:errors.append('Recording changed during this turn')
    except OSError:errors.append('Visual evidence unavailable at final validation')
  # Recheck pinned original versions immediately before publication.
  if w.one(db,"""select exists(select 1 from knowledge_qa.evidence e join knowledge.source_versions v on v.id=e.source_version_id
    where e.turn_id=%s and v.lifecycle_status<>'ACTIVE') stale""",(tid,))['stale']:errors.append('Evidence version changed during this turn; ask again')
  if w.one(db,"""select exists(select 1 from knowledge_qa.evidence e
    join analysis.records r on r.id=e.record_id join analysis.agent_outputs o on o.id=r.agent_output_id
    where e.turn_id=%s and (r.review_status='REJECTED' or o.validation_status<>'VALID'
      or r.review_status is distinct from e.snapshot->>'review_status'
      or exists(select 1 from analysis.run_sources rs join knowledge.source_versions sv on sv.id=rs.source_version_id
        where rs.run_id=r.run_id and sv.lifecycle_status<>'ACTIVE'))) stale""",(tid,))['stale']:
   errors.append('Saved review was rejected, reclassified or its evidence changed during this turn; ask again')
  if errors:raise ValueError('Answer cannot be published: '+'; '.join(errors))
 else:
  answer=None # Unverified drafts stay in audit events, never in the public final answer.
 w.q(db,'update knowledge_qa.turns set status=%s,answer=%s::jsonb,verification=%s::jsonb,completion_note=%s,completed_at=now() where id=%s',
  (status,w.j(answer),w.j(verdict),str(args.get('note',''))[:4000],tid));db.commit();return {'status':status}

def main(db,cfg,op,args):
 if op=='qa_attach':
  import chat_images
  return chat_images.attach(db,cfg,args)
 if op=='qa_begin':return begin(db,args)
 if op=='qa_event':return event(db,args)
 if op=='qa_retrieve':return retrieve(db,cfg,args)
 if op=='qa_finish':return finish(db,args)
 if op=='qa_validate':
  part=args['part'];obj=args['object']
  obj=canonical_normalization(args['original'],obj,args.get('recordings')) if part=='normalization' else obj
  errors=validate_normalization(args['original'],obj) if part=='normalization' else validate_answer(obj,args['evidence']) if part=='answer' else validate_verdict(obj,args['answer'],args.get('retrieval')) if part=='verdict' else ['Unknown contract']
  return {'object':obj,'valid':not errors,'errors':errors,'needs_investigation':part=='verdict' and may_investigate(obj,args.get('retrieval'))}
 if op=='qa_ready':ensure(db);return {'ready':True}
 if op=='qa_diagnose':
  import knowledge_search
  return knowledge_search.diagnose(db,cfg,args['query'])
 raise ValueError('Unknown QA operation')
