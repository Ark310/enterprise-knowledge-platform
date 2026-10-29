"""Whole-recording review adapter. Existing v2 targeted contracts are unchanged.
Never execute content. The host owns provenance, DB writes and the shared embedding profile.
"""
import json,re,uuid,subprocess,shutil,datetime
from pathlib import Path
import worker as w
CONTRACT='td-module-review-1.0'

def envelope(run_key,kind,payload):
 role='ARTICLE_REVIEW' if kind.startswith('DOCUMENTATION') else 'CURRENT_STATE'
 return dict(contract_version=CONTRACT,run_id=run_key,test_id='MODULE_REVIEW',module='Whole recording; modules identified in topic index',topic='Whole-recording documentation coverage',message_type=kind,sender=role,recipient='HUMAN' if role=='ARTICLE_REVIEW' else 'ARTICLE_REVIEW',status='PARTIAL',payload=payload,next_action='Host validates, saves and embeds; human factual review remains required.')

def validate(obj,kind,key):
 from jsonschema import Draft202012Validator
 schema=json.loads((w.BASE/'contracts/module-review.schema.json').read_text())
 errors=[x.message for x in Draft202012Validator(schema).iter_errors(obj)]
 if not errors and (obj['message_type']!=kind or obj['run_id']!=key):errors.append('Changed run ID or message type')
 return errors

def read(work,name):return json.loads((Path(work)/name).read_text(encoding='utf-8-sig'))
def write(work,name,obj):(Path(work)/name).write_text(w.j(obj),encoding='utf-8')
def duration(cfg,rec):
 ffmpeg=cfg.get('FFmpegExecutable') or shutil.which('ffmpeg')
 if not ffmpeg:raise ValueError('Whole-recording visual review requires ffmpeg; run Setup-POC.cmd')
 probe=Path(ffmpeg).with_name('ffprobe.exe' if Path(ffmpeg).suffix.lower()=='.exe' else 'ffprobe')
 probe=str(probe) if probe.is_file() else shutil.which('ffprobe')
 if probe:
  result=subprocess.run([probe,'-v','error','-show_entries','format=duration','-of','json',str(rec)],capture_output=True,text=True,timeout=30,check=True)
  value=float(json.loads(result.stdout)['format']['duration'])
 else:
  result=subprocess.run([ffmpeg,'-nostdin','-hide_banner','-i',str(rec)],capture_output=True,text=True,timeout=30)
  m=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',result.stderr)
  if not m:raise ValueError('Could not establish recording duration')
  value=int(m[1])*3600+int(m[2])*60+float(m[3])
 if not 0<value<86400:raise ValueError('Recording duration must be between 0 and 24 hours')
 return value,ffmpeg

def start(db,cfg,options):
 root=Path(cfg['DataRoot']);rec=w.safe_path(root,root/options['recording']);w.safe_path(root/'current-state',rec)
 if not rec.is_file() or rec.suffix.lower() not in w.VIDEO_EXT:raise ValueError('Choose an existing recording under current-state')
 srt=rec.with_suffix('.srt');w.safe_path(root,srt)
 if not srt.is_file():raise ValueError('Matching SRT is required; import the recording and SRT first')
 versions=[];hashes={}
 for p in (rec,srt):
  digest=w.file_hash(p);hashes[str(p)]=digest
  sv=w.one(db,"select id,content_sha256 from knowledge.source_versions where storage_uri=%s and lifecycle_status='ACTIVE' and evidence_role='CURRENT_STATE'",(p.absolute().as_uri(),))
  if not sv or sv['content_sha256']!=digest:raise ValueError('Run /process for this current revision first: '+p.name)
  versions.append(sv['id'])
 cues=w.q(db,"select a.id,a.content_text,a.locator,a.start_seconds,a.end_seconds from retrieval.active_content a join knowledge.extractions e on e.id=a.extraction_id where e.source_version_id=%s order by a.start_seconds",(versions[1],)).fetchall()
 if not cues:raise ValueError('No searchable transcript cues for this recording')
 seconds,ffmpeg=duration(cfg,rec)
 key='TD-MODULE-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex[:6]
 work=w.BASE/'runtime/runs'/key;work.mkdir(parents=True)
 sections=[]
 # 120 seconds at 2-second sampling = <=60 images per section, with all time intervals scheduled.
 for n,start_seconds in enumerate(range(0,__import__('math').ceil(seconds),120),1):
  sections.append({'id':f'S{n:03d}','start':start_seconds,'end':min(seconds,start_seconds+120)})
 rid=w.one(db,"insert into analysis.runs(run_key,module,topic,question,contract_version,agent_a_version,agent_b_version,status) values(%s,'Modules shown in recording','Whole-recording documentation coverage','Inventory recorded topics and assess documentation coverage',%s,'module-0.13','module-0.13','PROCESSING') returning id",(key,CONTRACT))['id']
 for sv in versions:w.q(db,"insert into analysis.run_sources(run_id,source_version_id,coverage_status,coverage_details) values(%s,%s,'LISTED',%s::jsonb)",(rid,sv,w.j({'review':'Whole recording in sampled sections; not continuous video or independent audio listening'})))
 manifest={'run_id':str(rid),'run_key':key,'recording_file':rec.relative_to(root).as_posix(),'transcript_file':srt.relative_to(root).as_posix(),'duration_seconds':seconds,'sections':sections,'hashes':hashes,'ffmpeg':ffmpeg,'transcript':cues,'scope':'Only topics shown or narrated in this recording, not every feature in the product/module. Frames sampled every two seconds; unobserved transitions remain unverified.'}
 write(work,'module-manifest.json',manifest)
 return {'work':str(work),'run_key':key,'sections':sections,'duration_seconds':seconds}

def section_packet(cfg,work,section_id):
 m=read(work,'module-manifest.json');s=next(x for x in m['sections'] if x['id']==section_id)
 rec=Path(cfg['DataRoot'])/m['recording_file']
 for path,digest in m['hashes'].items():
  if w.file_hash(path)!=digest:raise ValueError('Source changed during review; start a new review')
 folder=Path(work)/section_id;folder.mkdir(exist_ok=True)
 pattern=folder/'frame-%04d.jpg'
 decoded=subprocess.run([m['ffmpeg'],'-nostdin','-hide_banner','-loglevel','info','-ss',str(s['start']),'-i',str(rec),'-t',str(s['end']-s['start']),'-vf',"select='isnan(prev_selected_t)+gte(t-prev_selected_t,2)',scale=1280:-2,showinfo",'-vsync','vfr','-frames:v','60','-y',str(pattern)],capture_output=True,text=True,timeout=180,check=True)
 paths=sorted(folder.glob('frame-*.jpg'))
 times=[float(t) for t in re.findall(r'Parsed_showinfo[^\n]*pts_time:([0-9.]+)',decoded.stderr)]
 if len(times)<len(paths):raise ValueError('Could not map actual decoded frame timestamps')
 frames=[{'source_id':f"{s['start']+times[i]:.3f}",'seconds':s['start']+times[i],'path':str(p)} for i,p in enumerate(paths)]
 if not frames:raise ValueError('No frames decoded for section '+section_id)
 cues=[x for x in m['transcript'] if x['start_seconds'] is not None and float(x['end_seconds'])>=s['start'] and float(x['start_seconds'])<=s['end']]
 packet={'run_key':m['run_key'],'section':s,'recording_file':m['recording_file'],'transcript_file':m['transcript_file'],'transcript':cues,'frames':frames,'limitations':[m['scope'],'Original audio not independently listened to. Transcript timing is supplied, not independently aligned. Empty transcript intervals do not establish silence.']}
 for path,digest in m['hashes'].items():
  if w.file_hash(path)!=digest:raise ValueError('Source changed while preparing frames')
 write(folder,'evidence.json',packet)
 return packet

def check_section(work,obj,section_id):
 m=read(work,'module-manifest.json');errors=validate(obj,'CURRENT_STATE_SECTION',m['run_key'])
 if errors:return errors
 packet=read(Path(work)/section_id,'evidence.json');cues={str(x['id']):x for x in packet['transcript']};frames={x['source_id'] for x in packet['frames']}
 if obj['payload']['section_id']!=section_id:errors.append('Changed section ID')
 seen=set()
 for ob in obj['payload']['observations']:
  oid=ob['observation_id']
  if not re.fullmatch(section_id+r'-O\d+',oid) or oid in seen:errors.append('Invalid/duplicate observation ID')
  seen.add(oid);kinds={x['kind'] for x in ob['citations']}
  if ob['level'] in ('OBSERVED_VISUAL','CORROBORATED') and 'FRAME' not in kinds:errors.append('Visual claim lacks frame citation')
  if ob['level'] in ('NARRATED_ONLY','CORROBORATED') and 'TRANSCRIPT' not in kinds:errors.append('Narrated claim lacks transcript citation')
  for c in ob['citations']:
   if c['kind']=='FRAME' and c['source_id'] not in frames:errors.append('Frame timestamp not supplied')
   if c['kind']=='TRANSCRIPT' and (c['source_id'] not in cues or c['excerpt'] not in cues[c['source_id']]['content_text']):errors.append('Transcript ID/excerpt not supplied')
 return errors

def collect(work):
 m=read(work,'module-manifest.json');observations=[];limitations=[]
 for s in m['sections']:
  obj=read(Path(work)/s['id'],'a.json');errors=check_section(work,obj,s['id'])
  if errors:raise ValueError(w.j(errors))
  observations+=obj['payload']['observations'];limitations+=obj['payload']['limitations']
 if not observations:raise ValueError('No supported topics were extracted; no gap report can be claimed')
 return {'run_key':m['run_key'],'observations':observations,'limitations':list(dict.fromkeys(limitations))}

def check_index(obj,data):
 errors=validate(obj,'TOPIC_INDEX',data['run_key'])
 if errors:return errors
 original={x['observation_id']:x for x in data['observations']};refs=[];ids=[]
 for t in obj['payload']['topics']:
  ids.append(t['topic_id']);refs+=t['observation_ids']
  if len(set(t['observation_ids']))!=len(t['observation_ids']):errors.append('Repeated observation in topic')
  for ref in t['observation_ids']:
   if ref not in original:errors.append('Unknown observation reference')
   elif original[ref]['module']!=t['module']:errors.append('Topic changed original module attribution')
 if len(ids)!=len(set(ids)) or not all(re.fullmatch('T[0-9]+',x) for x in ids):errors.append('Invalid/duplicate topic IDs')
 if set(refs)!=set(original) or len(refs)!=len(original):errors.append('Every observation must be assigned to exactly one topic')
 return errors

def store(db,cfg,work,obj,role,records):
 m=read(work,'module-manifest.json');profile=w.model_profile(db,cfg);db.commit()
 oid=w.one(db,"insert into analysis.agent_outputs(run_id,agent_role,output_json,schema_validated,validation_status,validation_details,contract_schema_sha256,prompt_sha256,model_details) values(%s,%s,%s::jsonb,true,'VALID',%s::jsonb,%s,%s,%s::jsonb) returning id",(m['run_id'],role,w.j(obj),w.j({'checks':'module schema, coverage accounting, supplied citations; not human semantic approval'}),w.sha((w.BASE/'contracts/module-review.schema.json').read_bytes()),w.sha((w.BASE/'agents'/('agent-a-module.md' if role=='CURRENT_STATE' else 'agent-b-gaps.md')).read_bytes()),w.j({'engine':'Codex CLI','release':'0.13'})))['id']
 unitmap={str(x['id']):x for x in m['transcript']}
 if role=='ARTICLE_REVIEW':
  for packet in read(work,'gap-evidence.json')['topics']:
   for u in packet['passages']:unitmap[str(u['id'])]=u
 count=0
 for key,kind,topic,text,details,cites in records:
  rid=w.one(db,"insert into analysis.records(run_id,agent_output_id,record_key,record_type,topic,statement,evidence_level,details) values(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) returning id",(m['run_id'],oid,key,kind,topic,text,details.get('level'),w.j(details)))['id']
  for c in cites:
   uid=c.get('unit_id') or (c.get('source_id') if c.get('kind')=='TRANSCRIPT' else None)
   if uid and uid in unitmap:
    u=unitmap[uid];w.q(db,"insert into analysis.record_evidence(record_id,content_unit_id,relationship,locator,excerpt) values(%s,%s,'SUPPORTS',%s::jsonb,%s) on conflict do nothing",(rid,uid,w.j(u['locator']),c['excerpt']))
  if role=='ARTICLE_REVIEW':
   for ref in details['topic']['observation_ids']:
    upstream=w.one(db,'select id from analysis.records where run_id=%s and record_key=%s',(m['run_id'],'CURRENT_STATE:'+ref))
    if not upstream:raise ValueError('Missing A record for B topic linkage')
    w.q(db,"insert into analysis.record_links(from_record_id,to_record_id,relationship) values(%s,%s,'ASSESSES') on conflict do nothing",(rid,upstream['id']))
  embedded=(topic+'\n'+text)[:3000];w.progress(f"{role}: embedding {key} using {cfg['EmbeddingModel']} / {profile['id']}")
  v=w.embed(cfg,embedded);w.q(db,"insert into retrieval.analysis_embeddings(record_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s)",(rid,profile['id'],w.sha(embedded),w.vector(v),embedded));count+=1
 w.stage(db,m['run_id'],'AGENT_A' if role=='CURRENT_STATE' else 'AGENT_B','PARTIAL',{'records':count})
 w.stage(db,m['run_id'],'A_EMBED' if role=='CURRENT_STATE' else 'B_EMBED','COMPLETE',{'records':count,'profile_id':str(profile['id'])})
 return {'records':count,'profile_id':str(profile['id']),'output_id':str(oid)}

def save_a(db,cfg,work):
 data=collect(work);index=read(work,'topic-index.json');errors=check_index(index,data)
 if errors:raise ValueError(w.j(errors))
 obj=envelope(data['run_key'],'CURRENT_STATE_HANDOFF',{'observations':data['observations'],'topics':index['payload']['topics'],'limitations':data['limitations']+index['payload']['limitations']})
 errors=validate(obj,'CURRENT_STATE_HANDOFF',data['run_key'])
 if errors:raise ValueError(w.j(errors))
 records=[('CURRENT_STATE:'+x['observation_id'],'OBSERVATION',x['module']+' / '+x['topic'],x['statement'],x,x['citations']) for x in data['observations']]
 result=store(db,cfg,work,obj,'CURRENT_STATE',records);w.q(db,'update analysis.runs set module=%s where run_key=%s',('; '.join(dict.fromkeys(t['module'] for t in index['payload']['topics'])),data['run_key']));db.commit();write(work,'agent-a.json',obj);write(work,'validation-a.json',dict(valid=True,errors=[],**result));return result

def retrieve(db,cfg,work):
 m=read(work,'module-manifest.json');a=read(work,'agent-a.json');topics=[]
 for t in a['payload']['topics']:
  obs=[x for x in a['payload']['observations'] if x['observation_id'] in t['observation_ids']]
  # Audit actual executed queries, not model-invented search terms. Candidate bounds explicit.
  queries=list(dict.fromkeys([t['module']+' '+t['title'],t['title'],t['title']+' instructions setup configuration']))
  passages={}
  for query in queries:
   result=w.search(db,cfg,query,'EXISTING_ASSET',8)
   for u in result['passages']:passages[str(u['id'])]=u
  topics.append({'topic':t,'observations':obs,'executed_queries':queries,'passages':list(passages.values()),'coverage':'BOUNDED: at most 8 hybrid passages per query, up to 24 distinct passages. No company-wide absence claim.'})
  for u in passages.values():w.q(db,"insert into analysis.run_sources(run_id,source_version_id,coverage_status,coverage_details) values(%s,%s,'SEARCHED',%s::jsonb) on conflict(run_id,source_version_id) do nothing",(m['run_id'],u['version_id'],w.j({'topic_id':t['topic_id'],'bounded_candidate_packet':True})))
  db.commit();w.progress(f"B evidence: {t['topic_id']} {t['title']} — {len(passages)} passages")
 result={'run_key':m['run_key'],'topics':topics};write(work,'gap-evidence.json',result);return result

def check_rows(obj,data,expected_ids):
 errors=validate(obj,'DOCUMENTATION_GAP_BATCH',data['run_key'])
 if errors:return errors
 ids=[x['topic_id'] for x in obj['payload']['rows']]
 if set(ids)!=set(expected_ids) or len(ids)!=len(set(ids)):errors.append('Each requested topic must have exactly one coverage row')
 packets={x['topic']['topic_id']:x for x in data['topics']}
 for row in obj['payload']['rows']:
  if row['topic_id'] not in packets:continue
  units={str(x['id']):x for x in packets[row['topic_id']]['passages']}
  if row['coverage'] in ('COVERED','NEEDS_REWORK') and not row['article_citations']:errors.append('Existing coverage/rework needs supplied article citations')
  if row['coverage']=='NOT_FOUND_IN_REVIEWED_SOURCES' and (row['article_citations'] or row['unread_relevant_sources']):errors.append('Missing coverage cannot hide cited coverage or unread relevant sources; use NEEDS_REWORK/NEEDS_REVIEW')
  for c in row['article_citations']:
   if c['unit_id'] not in units or c['excerpt'] not in units[c['unit_id']]['content_text']:errors.append('Article citation ID/excerpt not in this topic evidence packet')
 return errors

def finalize(db,cfg,work):
 evidence=read(work,'gap-evidence.json');rows=[];limitations=[]
 # Each batch manifest is generated by the host; every indexed topic must be accounted for.
 for name in sorted(Path(work).glob('batches/batch-*.json')):
  batch=json.loads(name.read_text());obj=read(name.parent/name.stem,'b.json');errors=check_rows(obj,evidence,batch['topic_ids'])
  if errors:raise ValueError(w.j(errors))
  rows+=obj['payload']['rows'];limitations+=obj['payload']['limitations']
 expected=[x['topic']['topic_id'] for x in evidence['topics']]
 if len(rows)!=len(expected) or {r['topic_id'] for r in rows}!=set(expected):raise ValueError('Gap report omitted or duplicated topics')
 obj=envelope(evidence['run_key'],'DOCUMENTATION_GAP_REPORT',{'rows':rows,'limitations':list(dict.fromkeys(limitations))+['Qualified gaps concern reviewed sources only. Unshown features are outside this recording. Findings remain AGENT_PROPOSED.']})
 if validate(obj,'DOCUMENTATION_GAP_REPORT',evidence['run_key']):raise ValueError('Final report schema invalid')
 topics={x['topic']['topic_id']:x['topic'] for x in evidence['topics']}
 records=[]
 for row in rows:
  t=topics[row['topic_id']];details=dict(row,topic=t)
  records.append(('ARTICLE_REVIEW:'+t['topic_id'],'FINDING',t['module']+' / '+t['title'],row['coverage']+': '+row['reason']+'\nProposed work: '+'; '.join(row['actions']),details,row['article_citations']))
 result=store(db,cfg,work,obj,'ARTICLE_REVIEW',records)
 m=read(work,'module-manifest.json');w.q(db,"update analysis.runs set status='PARTIAL',completed_at=now() where id=%s",(m['run_id'],));w.stage(db,m['run_id'],'RETRIEVAL_READY','PARTIAL',{'topics':len(rows),'coverage':'sampled/ bounded; not human approved'});db.commit()
 write(work,'agent-b.json',obj);write(work,'validation-b.json',dict(valid=True,errors=[],**result));return results(db,evidence['run_key'])

def results(db,key):
 if key=='latest':run=w.one(db,"select * from analysis.runs where contract_version=%s order by created_at desc limit 1",(CONTRACT,))
 else:run=w.one(db,"select * from analysis.runs where contract_version=%s and (run_key=%s or id::text=%s)",(CONTRACT,key,key))
 if not run:raise ValueError('No whole-recording review found. Run /review first.')
 outputs=w.q(db,"select agent_role,output_json from analysis.agent_outputs where run_id=%s and validation_status='VALID' order by created_at",(run['id'],)).fetchall()
 a=next((x['output_json'] for x in outputs if x['agent_role']=='CURRENT_STATE'),None);b=next((x['output_json'] for x in outputs if x['agent_role']=='ARTICLE_REVIEW'),None)
 if not b:return {'run_key':run['run_key'],'run_id':str(run['id']),'status':run['status'],'message':'Gap report not complete; no final gap list is claimed.'}
 current=w.one(db,"select not exists(select 1 from analysis.run_sources rs join knowledge.source_versions sv on sv.id=rs.source_version_id where rs.run_id=%s and sv.lifecycle_status<>'ACTIVE') ok",(run['id'],))['ok']
 m=read(w.BASE/'runtime/runs'/run['run_key'],'module-manifest.json') if (w.BASE/'runtime/runs'/run['run_key']/'module-manifest.json').exists() else None
 rows=[];topics={t['topic_id']:t for t in a['payload']['topics']}
 # Resolve citations in PostgreSQL: exact run retrieval works even if old runtime files are not copied.
 for row in b['payload']['rows']:
  t=topics[row['topic_id']];cites=[]
  for c in row['article_citations']:
   unit=w.one(db,'select u.locator,s.title,s.source_url from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id join knowledge.source_versions v on v.id=e.source_version_id join knowledge.sources s on s.id=v.source_id where u.id=%s',(c['unit_id'],));cites.append(dict(c,locator=unit['locator'] if unit else None,article_title=unit['title'] if unit else None,source_url=unit['source_url'] if unit else None))
  observations=[x for x in a['payload']['observations'] if x['observation_id'] in t['observation_ids']]
  rows.append(dict(row,module=t['module'],title=t['title'],article_citations=cites,observations=observations))
 totals={s:sum(r['coverage']==s for r in rows) for s in ('COVERED','NEEDS_REWORK','NOT_FOUND_IN_REVIEWED_SOURCES','NEEDS_REVIEW')}
 return {'run_key':run['run_key'],'run_id':str(run['id']),'status':run['status'],'summary':totals,'source_revisions_current':current,'rows':rows,'limitations':b['payload']['limitations'],'coverage':m['scope'] if m else 'Whole recording sampled in sections; bounded documentation search; not human approved.'}

def main(db,cfg,op,args):
 work=args.get('work')
 if op=='module_start':return start(db,cfg,args)
 if op=='module_section':return section_packet(cfg,work,args['section_id'])
 if op=='module_check_section':
  obj=read(Path(work)/args['section_id'],'a.json');errors=check_section(work,obj,args['section_id']);write(Path(work)/args['section_id'],'validation.json',{'valid':not errors,'errors':errors});return {'valid':not errors,'errors':errors}
 if op=='module_collect':return collect(work)
 if op=='module_save_a':return save_a(db,cfg,work)
 if op=='module_retrieve':return retrieve(db,cfg,work)
 if op=='module_check_batch':
  folder=Path(work)/'batches'/args['batch_id'];obj=read(folder,'b.json');errors=check_rows(obj,read(work,'gap-evidence.json'),args['topic_ids']);write(folder,'validation.json',{'valid':not errors,'errors':errors});return {'valid':not errors,'errors':errors}
 if op=='module_finalize':return finalize(db,cfg,work)
 if op=='module_results':return results(db,args.get('run_key','latest'))
 raise ValueError('Unknown module review operation')
