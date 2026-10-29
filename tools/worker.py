"""TD 0.10 evidence worker. JSON stdin/stdout; progress to stderr. Never executes source files."""
import sys,os,json,re,hashlib,uuid,datetime,urllib.request,urllib.parse,zipfile,html,subprocess,shutil,traceback
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1]
VERSION='0.14.0'
EXTRACTION_VERSION='0.10.0' # Parser/chunk semantics unchanged; reuse successful v0.10 extractions
ROOTS=[('current-state','CURRENT_STATE'),('existing-assets/Confluence Articles','EXISTING_ASSET'),('existing-assets/REST API','EXISTING_ASSET'),('existing-assets/Sharepoint','EXISTING_ASSET'),('existing-assets/VLCs','EXISTING_ASSET')]
TEXT_EXT={'.txt','.md','.json','.csv','.html','.htm','.xml','.yaml','.yml','.cs','.go','.java','.js','.php','.py','.rb','.sh','.sql','.svg','.srt','.vtt','.log'}
VIDEO_EXT={'.mp4','.wmv','.mov','.mkv','.avi','.webm'}
def j(v):return json.dumps(v,ensure_ascii=False,default=str)
def sha(v):return hashlib.sha256(v.encode('utf-8') if isinstance(v,str) else v).hexdigest()
def progress(s):print(s,file=sys.stderr,flush=True)
def chunks(s,size=3000):return [s[i:i+size] for i in range(0,len(s),size)]
def srt_units(s):
 out=[]
 for i,b in enumerate(re.split(r'\n\s*\n',s.replace('\r','').strip())):
  if not b.strip():continue
  m=re.search(r'(\d+):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{3})[^\n]*\n(.*)',b,re.S)
  if not m:raise ValueError('Malformed subtitle cue '+str(i+1))
  a=list(map(int,m.groups()[:8]));start=a[0]*3600+a[1]*60+a[2]+a[3]/1000;end=a[4]*3600+a[5]*60+a[6]+a[7]/1000
  if end<=start:raise ValueError('Subtitle end must follow start')
  text=m.group(9).strip()
  if text:out.append({'text':text,'start':start,'end':end,'locator':{'cue':i+1,'start_seconds':start,'end_seconds':end},'kind':'SUPPLIED_TRANSCRIPT'})
 return out

def safe_path(root,path):
 root=Path(root).absolute();p=Path(path).absolute()
 try:p.relative_to(root)
 except ValueError:raise ValueError('Path outside approved root')
 cur=p
 while True:
  if cur.is_symlink() or (hasattr(cur,'is_junction') and cur.is_junction()) or (cur.exists() and getattr(cur.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Links/junctions/reparse points are excluded')
  if cur==root:break
  cur=cur.parent
 return p

def file_hash(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def scan(cfg):
 root=Path(cfg['DataRoot']).absolute();files=[];errors=[];skipped=[]
 for rel,role in ROOTS:
  folder=root/rel
  if not folder.is_dir():errors.append({'path':str(folder),'error':'Included folder missing'});continue
  def onerror(e):errors.append({'path':str(e.filename),'error':str(e)})
  for d,dirs,names in os.walk(folder,followlinks=False,onerror=onerror):
   for n in dirs[:]:
    try:safe_path(root,Path(d)/n)
    except ValueError:dirs.remove(n);skipped.append(str(Path(d)/n))
   for n in sorted(names):
    p=Path(d)/n
    if n.startswith('~$'):skipped.append(str(p));continue
    try:
     safe_path(root,p);before=p.stat();digest=file_hash(p);after=p.stat()
     if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('File changed during scan; retry after copy completes')
     files.append({'path':str(p),'relative':p.relative_to(root).as_posix(),'role':role,'group':'current-state' if role=='CURRENT_STATE' else 'existing-assets','sha256':digest,'bytes':after.st_size,'modified':datetime.datetime.fromtimestamp(after.st_mtime,datetime.timezone.utc).isoformat()})
    except Exception as e:errors.append({'path':str(p),'error':str(e)})
 files.sort(key=lambda x:x['relative'].lower())
 return {'files':files,'errors':errors,'skipped_links_or_temporary':skipped,'complete':not errors,'excluded':['existing-assets/Meeting Recordings'],'scanned_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}

def decode(b):
 for enc in ['utf-8-sig','utf-16','cp1252']:
  try:return b.decode(enc)
  except UnicodeError:pass
 raise ValueError('Unknown text encoding')

def extract(path):
 p=Path(path);ext=p.suffix.lower();out=[];warnings=[];meta={};status='COMPLETE'
 def add(text,loc,**kw):
  for i,t in enumerate(chunks(text)):
   out.append({'text':t,'locator':dict(loc,part=i+1),**kw})
 if ext in VIDEO_EXT:return {'status':'BLOCKED','units':[],'warnings':['Video registered; visual review is scoped to agent runs. Transcript is separately imported.'],'metadata':{}}
 if ext=='.srt':out=srt_units(decode(p.read_bytes()))
 elif ext in TEXT_EXT:
  s=decode(p.read_bytes())
  if ext=='.json':
   data=json.loads(s);meta={'json':data}
   # Article JSON and markdown exports retain separate physical provenance. Search prefers article text.
   if isinstance(data,dict) and isinstance(data.get('content'),dict):
    content=data['content'];s=content.get('text') or content.get('markdown') or s
    product=data.get('product');meta['product']=product.get('key') if isinstance(product,dict) else product
    meta['title']=data.get('title');meta['url']=data.get('url');meta['page_id']=data.get('page_id')
   else:s=json.dumps(data,ensure_ascii=False,indent=2)
  elif ext in {'.html','.htm'}:s=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I)))
  for n,line in enumerate(s.splitlines(keepends=True),1):
   # Joining lines below gives compact passages while preserving line ranges.
   pass
  lines=s.splitlines(keepends=True);buf='';start=1
  for n,line in enumerate(lines,1):
   if len(buf)+len(line)>3000 and buf:add(buf,{'line_start':start,'line_end':n-1});buf='';start=n
   buf+=line
  if buf:add(buf,{'line_start':start,'line_end':len(lines)})
 elif ext=='.docx':
  with zipfile.ZipFile(p) as z:
   root=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
   for n,para in enumerate(root.findall('.//w:p',ns),1):
    t=''.join(x.text or '' for x in para.findall('.//w:t',ns))
    if t.strip():add(t,{'paragraph':n})
 elif ext in {'.xlsx','.xls'}:
  if ext=='.xlsx':
   import openpyxl
   book=openpyxl.load_workbook(p,read_only=True,data_only=False)
   for sheet in book:
    for n,row in enumerate(sheet.iter_rows(values_only=True),1):
     text=' | '.join('' if x is None else str(x) for x in row)
     if text.replace('|','').strip():add(text,{'sheet':sheet.title,'row':n},sheet=sheet.title,cell_range=f'A{n}:{openpyxl.utils.get_column_letter(len(row))}{n}')
   book.close()
  else:
   import xlrd
   book=xlrd.open_workbook(p)
   for sheet in book.sheets():
    for n in range(sheet.nrows):add(' | '.join(map(str,sheet.row_values(n))),{'sheet':sheet.name,'row':n+1},sheet=sheet.name)
 elif ext=='.pdf':
  from pypdf import PdfReader
  reader=PdfReader(p)
  for n,page in enumerate(reader.pages,1):
   text=page.extract_text() or ''
   if text.strip():add(text,{'page':n},page=n)
   else:warnings.append(f'Page {n} has no extracted text; OCR pending')
  if warnings:status='PARTIAL'
 else:return {'status':'BLOCKED','units':[],'warnings':['Unsupported binary/image extraction. Conversion/OCR is pending; not searchable.'],'metadata':{}}
 out=[u for u in out if u['text'].strip()]
 if not out:warnings.append('No usable text extracted');status='PARTIAL'
 return {'status':status,'units':out,'warnings':warnings,'metadata':meta}

def connect():
 import psycopg
 from psycopg.rows import dict_row
 conn=os.environ.get('TD_PG_CONNECTION','')
 if not conn:raise ValueError('TD_PG_CONNECTION is unset. Run Configure-Database.cmd once.')
 return psycopg.connect(conn,row_factory=dict_row,connect_timeout=10,prepare_threshold=None)

def q(db,sql,args=()):return db.execute(sql,args if args else None)
def one(db,sql,args=()):return q(db,sql,args).fetchone()
def require_db(db):
 r=one(db,"select current_database() db,(select extversion from pg_extension where extname='vector') vector")
 if r['db']!='knowledge_poc' or not r['vector']:raise ValueError('Expected knowledge_poc with vector enabled')
 if one(db,"select to_regclass('knowledge.source_groups') t")['t'] is None:raise ValueError('Install approved v0.3 schema first')

def migration(db):
 require_db(db)
 q(db,(BASE/'database/migrations/010-local-files.sql').read_text(encoding='utf-8-sig'))

def ollama(cfg,endpoint,body=None):
 url=cfg.get('OllamaUrl','http://localhost:11434').rstrip('/')+endpoint
 # Credentials and extracted content must not be sent to arbitrary destinations by source data.
 if urllib.parse.urlparse(url).hostname not in {'localhost','127.0.0.1','::1'}:raise ValueError('OllamaUrl must be loopback for local POC')
 req=urllib.request.Request(url,data=None if body is None else j(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=600) as r:return json.load(r)

def model_profile(db,cfg):
 model=cfg['EmbeddingModel'];tags=ollama(cfg,'/api/tags')['models'];tag=next((x for x in tags if x['name']==model or x.get('model')==model),None)
 if not tag:raise ValueError('Embedding model missing. Run Setup-LocalModel.cmd')
 digest=tag['digest'];vec=embed(cfg,'profile dimension check',False);dims=len(vec)
 key='ollama:'+model+':'+digest+':td-chars3000-v1'
 row=one(db,"select * from retrieval.embedding_profiles where profile_key=%s",(key,))
 if not row:
  row=one(db,"""insert into retrieval.embedding_profiles(profile_key,provider,model,model_revision,dimensions,distance_metric,preprocessing_version)
  values(%s,'OLLAMA',%s,%s,%s,'COSINE','td-chars3000-v1/query-instruction-v1') returning *""",(key,model,digest,dims))
 return row

def embed(cfg,text,is_query=False):
 if is_query:text='Instruct: Given a question about Contoso product documentation, retrieve passages that answer the question\nQuery: '+text
 r=ollama(cfg,'/api/embed',{'model':cfg['EmbeddingModel'],'input':text,'truncate':False,'keep_alive':'30m','options':{'num_ctx':4096,'num_batch':64}})
 v=r['embeddings'][0]
 if not v or not all(isinstance(x,(int,float)) and __import__('math').isfinite(x) for x in v):raise ValueError('Invalid vector')
 return v

def vector(v):return '['+','.join(str(x) for x in v)+']'
def source_type(p):
 e=Path(p).suffix.lower()
 if e in VIDEO_EXT:return 'RECORDING'
 return {'.srt':'TRANSCRIPT','.docx':'DOCUMENT','.doc':'DOCUMENT','.pdf':'DOCUMENT','.xlsx':'WORKBOOK','.xls':'WORKBOOK','.png':'SCREENSHOT','.jpg':'SCREENSHOT','.json':('API_SPEC' if 'REST API' in str(p) else 'OTHER'),'.md':'ARTICLE','.html':'ARTICLE'}.get(e,'OTHER')
def mime(p):return __import__('mimetypes').guess_type(str(p))[0] or 'application/octet-stream'

def register(db,f):
 group=one(db,'select id from knowledge.source_groups where group_key=%s',(f['group'],))
 if not group:raise ValueError('Missing approved source group '+f['group'])
 gid=group['id'];uri=Path(f['path']).absolute().as_uri();meta={'local_relative':f['relative'],'local_path':f['path'],'provider':'LOCAL','scope':'five approved roots'}
 obj=one(db,"""insert into knowledge.storage_objects(group_id,object_key,object_kind,title,mime_type,original_url,metadata)
 values(%s,%s,'LOCAL_FILE',%s,%s,%s,%s::jsonb) on conflict(group_id,object_key) do update set last_seen_at=now(),availability='AVAILABLE',metadata=excluded.metadata returning id""",(gid,'local:'+f['relative'].lower(),Path(f['path']).name,mime(f['path']),uri,j(meta)))['id']
 ov=one(db,"""insert into knowledge.object_versions(object_id,version_key,byte_size,sha256,storage_uri,read_status,provider_modified_at)
 values(%s,%s,%s,%s,%s,'READABLE',%s) on conflict(object_id,version_key) do update set read_status='READABLE' returning id""",(obj,f['sha256'],f['bytes'],f['sha256'],uri,f['modified']))['id']
 sid=one(db,"""insert into knowledge.sources(source_system,external_namespace,external_key,source_type,title,source_url)
 values('LOCAL_FOLDER',%s,%s,%s,%s,%s) on conflict(source_system,external_namespace,external_key) do update set title=excluded.title returning id""",(f['group'],f['relative'].lower(),source_type(f['path']),Path(f['path']).name,uri))['id']
 sv=one(db,"""insert into knowledge.source_versions(source_id,revision_key,evidence_role,storage_uri,mime_type,byte_size,content_sha256,source_modified_at,group_id,metadata)
 values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) on conflict(source_id,revision_key) do update set lifecycle_status='ACTIVE' returning id""",(sid,f['sha256'],f['role'],uri,mime(f['path']),f['bytes'],f['sha256'],f['modified'],gid,j(meta)))['id']
 q(db,"insert into knowledge.version_representations(source_version_id,object_version_id,representation_role) values(%s,%s,'PRIMARY') on conflict do nothing",(sv,ov))
 q(db,"update knowledge.source_versions set lifecycle_status='SUPERSEDED' where source_id=%s and id<>%s and lifecycle_status='ACTIVE'",(sid,sv))
 return sv,ov

def job(db,ov,operation,status,details):
 conf=sha('td-v010-'+operation)
 q(db,"""insert into knowledge.ingestion_jobs(object_version_id,operation,processor_version,config_sha256,attempt,status,started_at,finished_at,error_details)
 select %s,%s,%s,%s,coalesce(max(attempt),0)+1,%s,now(),now(),%s::jsonb from knowledge.ingestion_jobs where object_version_id=%s and operation=%s and processor_version=%s and config_sha256=%s""",(ov,operation,VERSION,conf,status,j(details),ov,operation,VERSION,conf))

def ingest_api(db,sv,ov,data,file):
 """Preserve version-scoped documentary endpoints, nested parameters and raw response labels."""
 endpoint=data.get('endpoint') if isinstance(data,dict) else None
 if not isinstance(endpoint,dict) or not endpoint.get('method') or not endpoint.get('path'):return
 op=one(db,"""insert into knowledge.api_operations(source_version_id,operation_key,method_raw,path_raw,request_url_raw,source_locator,raw_definition,metadata)
 values(%s,'endpoint',%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb) on conflict(source_version_id,operation_key) do update set raw_definition=excluded.raw_definition returning id""",(sv,str(endpoint['method']),str(endpoint['path']),endpoint.get('request_url'),j({'file':file,'json_path':'$.endpoint'}),j(endpoint),j({'page_id':data.get('page_id'),'upstream_url':data.get('url'),'source':'documentation capture; never executed'})))['id']
 def params(items,location,parent=None,prefix='',response=None):
  for n,item in enumerate(items or []):
   if not isinstance(item,dict):continue
   key=prefix+'/'+str(n);required=item.get('required');required=required if isinstance(required,bool) else None
   rid=one(db,"""insert into knowledge.api_parameters(operation_id,response_example_id,parent_parameter_id,parameter_key,location,name,data_type_raw,required_claim,description,example_value,ordinal,source_locator,raw_definition)
   values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb) on conflict(operation_id,parameter_key) do update set raw_definition=excluded.raw_definition returning id""",(op,response,parent,location+key,location,str(item.get('name','')),str(item.get('type','')),required,item.get('description'),j(item.get('example')),n,j({'file':file,'json_path':'$.endpoint.'+location+key}),j(item)))['id']
   params(item.get('children',[]),location,rid,key,response)
 for field,location in [('headers','HEADER'),('path_params','PATH'),('query','QUERY'),('body','BODY')]:params(endpoint.get(field,[]),location)
 def example(key,kind,context,body,rawstatus=None,language=None):
  label=None if rawstatus is None else str(rawstatus);numeric=int(label) if label and re.fullmatch(r'[1-5][0-9]{2}',label) else None
  text=body if isinstance(body,str) else j(body);structured=None
  try:structured=json.loads(text)
  except Exception:pass
  return one(db,"""insert into knowledge.api_examples(operation_id,example_key,example_kind,context,language,status_label_raw,http_status,body_text,structured_body,payload_status,source_object_version_id,source_locator)
  values(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb) on conflict(operation_id,example_key) do update set body_text=excluded.body_text returning id""",(op,key,kind,context,language,label,numeric,text,j(structured),'PRESENT' if text.strip() else 'EMPTY',ov,j({'file':file,'json_path':key})))['id']
 for n,r in enumerate(endpoint.get('responses',[]) or []):
  if isinstance(r,dict):
   response=example('response/'+str(n),'RESPONSE','REFERENCE',r.get('example',''),r.get('status'))
   params(r.get('params',[]),'RESPONSE',prefix='/response'+str(n),response=response)
 for n,s in enumerate(data.get('snippets',[]) or []):
  if isinstance(s,dict):example('snippet/'+str(n),'CODE_SAMPLE','REFERENCE',s.get('code',''),language=s.get('language'))
 if isinstance(data.get('tryit'),dict):example('tryit','TRYIT_CAPTURE','TRYIT',data['tryit'])


def process(cfg,options):
 inventory=scan(cfg);totals={'registered':0,'extracted':0,'blocked':0,'failed':0,'embedded':0,'unchanged':0,'failures':[],'scan_errors':inventory['errors']}
 limit=int(options.get('limit',0));selected=inventory['files'][:limit] if limit>0 else inventory['files']
 with connect() as db:
  require_db(db)
  if not one(db,"select exists(select 1 from pg_constraint where conname='td_local_file_shape_v010') ok")['ok']:raise ValueError('Run Initialize-Database.cmd local-file migration first')
  # One session advisory lock prevents multiple embedding/import workers.
  if not one(db,'select pg_try_advisory_lock(107010) ok')['ok']:raise ValueError('Another processing worker is active')
  profile=model_profile(db,cfg);db.commit()
  batch=one(db,"insert into knowledge.intake_batches(batch_key,declared_scope,scan_status,manifest_reconciliation,notes) values(%s,%s::jsonb,%s,'NO_MANIFEST',%s::jsonb) returning id",('local-'+str(uuid.uuid4()),j({'roots':ROOTS,'limit':limit}),'PARTIAL' if inventory['errors'] or limit else 'COMPLETE',j({'errors':inventory['errors'],'exclusions':inventory['excluded']})))['id'];db.commit()
  for i,f in enumerate(selected,1):
   progress(f"[{i}/{len(selected)}] {f['relative']}")
   committed=False;before_counts={k:totals[k] for k in ['registered','extracted','blocked','unchanged']}
   try:
    if file_hash(f['path'])!=f['sha256']:raise ValueError('File changed after scan')
    with db.transaction():
     sv,ov=register(db,f);totals['registered']+=1
     q(db,"insert into knowledge.intake_entries(batch_id,group_id,entry_key,member_path,expected_bytes,expected_sha256,observed_object_version_id,presence_status,review_status) select %s,group_id,%s,%s,%s,%s,%s,'PRESENT','INVENTORIED' from knowledge.source_versions where id=%s",(batch,f['relative'],f['relative'],f['bytes'],f['sha256'],ov,sv))
     ex=one(db,"select id,status from knowledge.extractions where source_version_id=%s and is_active and processor_version=%s",(sv,EXTRACTION_VERSION))
     if not ex:
      data=extract(f['path'])
      if file_hash(f['path'])!=f['sha256']:raise ValueError('File changed while extracting; transaction rolled back')
      if data['metadata'].get('title'):q(db,"update knowledge.sources set title=%s,product=%s,source_url=coalesce(%s,source_url),source_type='ARTICLE' where id=(select source_id from knowledge.source_versions where id=%s)",(data['metadata']['title'],data['metadata'].get('product'),data['metadata'].get('url'),sv))
      status=data['status'];q(db,'update knowledge.extractions set is_active=false where source_version_id=%s',(sv,))
      ex=one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,warnings,is_active) values(%s,'LOCAL_PARSER',%s,%s,%s::jsonb,%s) returning id,status",(sv,EXTRACTION_VERSION,'PARTIAL' if status=='BLOCKED' else status,j(data['warnings']),status!='BLOCKED'))
      for n,u in enumerate(data['units']):
       loc=dict(u['locator'],file=f['relative'],source_version_id=str(sv))
       q(db,"""insert into knowledge.content_units(extraction_id,unit_key,unit_type,heading,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds,page_number,sheet_name,cell_range)
       values(%s,%s,'PASSAGE',%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)""",(ex['id'],str(n),Path(f['path']).name,u['text'],u.get('kind','SOURCE_TEXT'),j(loc),sha(u['text']),u.get('start'),u.get('end'),u.get('page'),u.get('sheet'),u.get('cell_range')))
      ingest_api(db,sv,ov,data['metadata'].get('json',{}),f['relative'])
      job(db,ov,'EXTRACT',status,{'warnings':data['warnings'],'unit_count':len(data['units'])})
      if status=='BLOCKED':totals['blocked']+=1
      else:totals['extracted']+=1
     else:totals['unchanged']+=1
    db.commit();committed=True
    pending=q(db,"select u.id,u.content_text from knowledge.content_units u where u.extraction_id=%s and u.content_status='USABLE' and not exists(select 1 from retrieval.content_embeddings e where e.content_unit_id=u.id and e.profile_id=%s)",(ex['id'],profile['id'])).fetchall();db.commit()
    for u in pending:
     v=embed(cfg,u['content_text'])
     if len(v)!=profile['dimensions']:raise ValueError('Embedding dimensions changed')
     q(db,"insert into retrieval.content_embeddings(content_unit_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s) on conflict do nothing",(u['id'],profile['id'],sha(u['content_text']),vector(v),u['content_text']));db.commit();totals['embedded']+=1
    count=one(db,'select count(*) n from knowledge.content_units where extraction_id=%s',(ex['id'],))['n']
    job(db,ov,'EMBED','COMPLETE' if count else 'BLOCKED',{'profile_id':str(profile['id']),'new_vectors':len(pending),'reason':None if count else 'No searchable units; conversion or scoped video review required'});db.commit()
   except Exception as e:
    db.rollback()
    if not committed:
     for k,v in before_counts.items():totals[k]=v
    totals['failed']+=1;totals['failures'].append({'file':f['relative'],'error':str(e)});progress('FAILED '+f['relative']+': '+str(e))
    # Persist a failure separately when physical registration already committed.
    existing=one(db,"select id from knowledge.object_versions where storage_uri=%s and sha256=%s",(Path(f['path']).absolute().as_uri(),f['sha256']))
    if existing:job(db,existing['id'],'EMBED','FAILED',{'message':str(e)})
    db.commit()
  q(db,"update knowledge.intake_batches set notes=notes || %s::jsonb where id=%s",(j({'processing_summary':totals}),batch));db.commit()
  return totals

def status(db):
 require_db(db)
 return {'sources':one(db,'select count(*) n from knowledge.sources')['n'],'active_versions':one(db,"select count(*) n from knowledge.source_versions where lifecycle_status='ACTIVE'")['n'],'searchable_units':one(db,'select count(*) n from retrieval.active_content')['n'],'vectors':one(db,'select count(*) n from retrieval.content_embeddings')['n'],'extraction_jobs':q(db,'select status,count(*) n from knowledge.ingestion_jobs group by status').fetchall(),'runs':q(db,'select run_key,status,created_at from analysis.runs order by created_at desc limit 10').fetchall()}

def search(db,cfg,text,role=None,limit=20):
 require_db(db);limit=max(1,min(int(limit),80));profile=model_profile(db,cfg);queryvec=vector(embed(cfg,text,True));db.commit()
 # Reciprocal rank fusion rather than adding incompatible raw text/cosine scores.
 rows=q(db,"""with base as(select a.*,s.title,s.product,v.id version_id from retrieval.active_content a join knowledge.extractions ex on ex.id=a.extraction_id join knowledge.source_versions v on v.id=ex.source_version_id join knowledge.sources s on s.id=v.source_id where (%s::text is null or a.evidence_role=%s)),
 lexical as(select id,row_number() over(order by ts_rank_cd(search_text,plainto_tsquery('simple',%s)) desc) rank from base where search_text @@ plainto_tsquery('simple',%s) limit 100),
 semantic as(select b.id,row_number() over(order by e.embedding <=> %s::vector) rank from base b join retrieval.content_embeddings e on e.content_unit_id=b.id and e.profile_id=%s order by e.embedding <=> %s::vector limit 100),
 scores as(select id,sum(score) score from(select id,1.0/(60+rank) score from lexical union all select id,1.0/(60+rank) from semantic) x group by id)
 select b.id,b.version_id,b.title,b.product,b.evidence_role,b.content_text,b.representation_kind,b.locator,b.storage_uri,b.start_seconds,b.end_seconds,scores.score from scores join base b using(id) order by scores.score desc limit %s""",(role,role,text,text,queryvec,profile['id'],queryvec,limit)).fetchall()
 derived=q(db,"""select r.id,r.run_id,r.record_key,r.statement,r.details,r.review_status,exists(select 1 from analysis.run_sources rs join knowledge.source_versions sv on sv.id=rs.source_version_id where rs.run_id=r.run_id and sv.lifecycle_status<>'ACTIVE') evidence_superseded from analysis.records r join analysis.agent_outputs o on o.id=r.agent_output_id join retrieval.analysis_embeddings e on e.record_id=r.id and e.profile_id=%s where o.validation_status='VALID' and r.review_status<>'REJECTED' order by e.embedding <=> %s::vector limit 8""",(profile['id'],queryvec)).fetchall()
 return {'passages':rows,'derived_findings':derived,'coverage':'Bounded hybrid search; not an exhaustive inventory. Findings are proposals, may be stale and must be checked against current source versions.'}

def validate_contract(obj,expected=None,request=None):
 from jsonschema import Draft202012Validator
 schema=json.loads((BASE/'contracts/contracts-v2.schema.json').read_text(encoding='utf-8-sig'))
 errors=[e.json_path+': '+e.message for e in Draft202012Validator(schema).iter_errors(obj)]
 if not isinstance(obj,dict):return errors or ['Expected a JSON object']
 if errors:return errors
 if expected and obj.get('message_type')!=expected:errors.append('Unexpected message_type')
 payload=obj.get('payload',{});ranges=payload.get('review_ranges',payload.get('request',{}).get('review_ranges',[]))
 for r in ranges:
  if r.get('end_seconds',0)<=r.get('start_seconds',0):errors.append('Review range end must follow start')
 if request:
  for key in ['run_id','test_id','module','topic','contract_version']:
   if obj.get(key)!=request.get(key):errors.append('Changed envelope field '+key)
  if obj.get('payload',{}).get('request')!=request.get('payload'):errors.append('Original request changed')
 return errors

def prepare_test(db,cfg,options):
 request=json.loads(Path(options['request_path']).read_text(encoding='utf-8-sig'));errors=validate_contract(request,'START_CURRENT_STATE')
 if errors:raise ValueError(j(errors))
 root=Path(cfg['DataRoot']);rel=options['recording'];rec=safe_path(root/'current-state',(root/rel).resolve())
 if not rel.replace('\\','/').startswith('current-state/'):raise ValueError('Recording must be in current-state')
 if rec.suffix.lower() not in VIDEO_EXT or not rec.is_file():raise ValueError('Recording not found')
 srt=rec.with_suffix('.srt')
 if not srt.is_file():raise ValueError('Matching basename .srt missing; process only after both are present')
 safe_path(root,srt)
 # Create local launch derived from original case; old original is never modified.
 request['run_id']=request['run_id']+'-LOCAL-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S')
 request['payload']['current_state_zip']='LOCAL_CURRENT_STATE';request['payload']['existing_assets_zip']='LOCAL_EXISTING_ASSETS';request['payload']['recording_member']=rec.relative_to(root).as_posix()
 request['payload']['target_context']+=' LOCAL ADAPTER: supplied timestamped transcript is '+srt.relative_to(root).as_posix()+'. Both use original-video time; matching name is pairing evidence, not independent alignment verification. Logical archive labels map to local roots in evidence manifest.'
 request['next_action']='Process locally through controlled v0.10 handoff.'
 packet=[]
 for p in [rec,srt]:
  uri=p.absolute().as_uri();sv=one(db,"select id,content_sha256 from knowledge.source_versions where storage_uri=%s and lifecycle_status='ACTIVE' and evidence_role='CURRENT_STATE'",(uri,))
  if not sv or sv['content_sha256']!=file_hash(p):raise ValueError('Recording/SRT not imported at current revision. Select Process first: '+p.name)
  if p==srt:
   packet=q(db,"select a.id,a.content_text,a.locator,a.start_seconds,a.end_seconds from retrieval.active_content a join knowledge.extractions e on e.id=a.extraction_id where e.source_version_id=%s order by a.start_seconds",(sv['id'],)).fetchall()
 ranges=request['payload']['review_ranges'];packet=[x for x in packet if x['start_seconds'] is not None and any(float(x['end_seconds'])>=r['start_seconds'] and float(x['start_seconds'])<=r['end_seconds'] for r in ranges)]
 if not packet:raise ValueError('No imported SRT cues overlap requested time range')
 expected_recording_hash=file_hash(rec);expected_srt_hash=file_hash(srt)
 work=BASE/'runtime/runs'/request['run_id'];work.mkdir(parents=True,exist_ok=False);frames=[];ffmpeg=cfg.get('FFmpegExecutable') or shutil.which('ffmpeg')
 if ffmpeg:
  # Scoped 2-second sampling. An agent must flag unobserved transitions; denser inspection remains necessary for brief actions.
  for n,r in enumerate(ranges):
   if r['end_seconds']<=r['start_seconds'] or r['end_seconds']-r['start_seconds']>600:raise ValueError('Each visual range must be positive and at most 600 seconds')
   duration=r['end_seconds']-r['start_seconds'];pattern=work/f'range{n}-%05d.jpg'
   cmd=[ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-ss',str(r['start_seconds']),'-i',str(rec),'-t',str(duration),'-vf','fps=1/2,scale=1280:-2','-frames:v','80',str(pattern)]
   subprocess.run(cmd,check=True,timeout=180,capture_output=True)
   for i,p in enumerate(sorted(work.glob(f'range{n}-*.jpg'))):frames.append({'path':str(p),'recording_file':rec.relative_to(root).as_posix(),'seconds':r['start_seconds']+i*2,'sampling':'2-second frames; actions between frames unverified'})
 manifest={'request':request,'transcript_file':srt.relative_to(root).as_posix(),'transcript':packet,'frames':frames,'original_audio_listened':False,'visual_limitations':[] if frames else ['ffmpeg unavailable: no visual evidence supplied; no visual/corroborated claims permitted'],'archive_mapping':{'LOCAL_CURRENT_STATE':str(root/'current-state'),'LOCAL_EXISTING_ASSETS':'four approved existing-assets roots'},'recording_sha256':expected_recording_hash,'srt_sha256':expected_srt_hash}
 if file_hash(rec)!=manifest['recording_sha256'] or file_hash(srt)!=manifest['srt_sha256']:raise ValueError('Recording/transcript changed while preparing frames; retry')
 (work/'request.json').write_text(j(request),encoding='utf-8');(work/'evidence-a.json').write_text(j(manifest),encoding='utf-8')
 rid=one(db,"insert into analysis.runs(run_key,module,topic,question,contract_version,agent_a_version,agent_b_version,status) values(%s,%s,%s,%s,%s,'2.1.0+local-0.12','2.1.0+local-0.12','PROCESSING') returning id",(request['run_id'],request['module'],request['topic'],request['payload']['question'],request['contract_version']))['id']
 for p in [rec,srt]:
  sv=one(db,"select id from knowledge.source_versions where storage_uri=%s and lifecycle_status='ACTIVE'",(p.absolute().as_uri(),))['id'];q(db,"insert into analysis.run_sources(run_id,source_version_id,coverage_status,coverage_details) values(%s,%s,'LISTED',%s::jsonb)",(rid,sv,j({'actual_coverage':'packet supplied; model inspection not independently established'})))
 return {'run_id':rid,'work':str(work),'request':request,'frames':frames,'evidence':manifest}

def stage(db,rid,name,status_,details):
 q(db,"""insert into analysis.stages(run_id,stage,attempt,status,started_at,completed_at,details) select %s,%s,coalesce(max(attempt),0)+1,%s,now(),now(),%s::jsonb from analysis.stages where run_id=%s and stage=%s""",(rid,name,status_,j(details),rid,name))

def citation_errors(obj,manifest,passages):
 errors=[];allowed={manifest['transcript_file']:manifest['transcript']};visual=manifest['request']['payload']['recording_member'];frames=manifest['frames']
 for p in passages:allowed.setdefault(p['locator']['file'],[]).append(p)
 def frame_matches(c):
  m=re.fullmatch(r'frame_seconds=([0-9]+(?:\.[0-9]+)?)',c.get('locator',''))
  return bool(m and any(abs(float(m.group(1))-float(f['seconds']))<0.001 for f in frames))
 def text_matches(c):
  try:loc=json.loads(c['locator'])
  except Exception:return False
  return any(loc==p.get('locator') and c['excerpt_or_observation'] in p.get('content_text','') for p in allowed.get(c['file'],[]))
 def visit(x):
  if isinstance(x,dict):
   if {'source_type','file','locator','excerpt_or_observation'}<=set(x):
    file=x['file'];typ=x['source_type']
    if typ=='HUMAN_REVIEW':errors.append('Agent may not fabricate human review')
    elif typ=='RECORDING_VISUAL':
     if file!=visual or not frame_matches(x):errors.append('Visual citation must identify an actually supplied frame timestamp')
    elif file not in allowed:errors.append('Citation outside supplied evidence: '+file)
    elif not text_matches(x):errors.append('Text citation must copy a supplied locator JSON and an exact excerpt: '+file)
   for v in x.values():visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(obj)
 for ob in obj.get('payload',{}).get('observations',[]):
  types={c['source_type'] for c in ob.get('citations',[])};level=ob.get('level')
  if level in {'OBSERVED_VISUAL','CORROBORATED'} and 'RECORDING_VISUAL' not in types:errors.append('Visual/corroborated observation requires visual citation')
  if level in {'NARRATED_ONLY','CORROBORATED'} and 'RECORDING_AUDIO_TRANSCRIPT' not in types:errors.append('Narrated/corroborated observation requires transcript citation')
 return errors

def save_output(db,cfg,options):
 work=Path(options['work']);manifest=json.loads((work/'evidence-a.json').read_text(encoding='utf-8-sig'));req=manifest['request'];role=options['role'];obj=json.loads(Path(options['output']).read_text(encoding='utf-8-sig'));expected='CURRENT_STATE_HANDOFF' if role=='CURRENT_STATE' else 'ARTICLE_ASSESSMENT'
 passages=json.loads((work/'evidence-b.json').read_text(encoding='utf-8-sig')).get('passages',[]) if (work/'evidence-b.json').exists() else []
 errors=validate_contract(obj,expected,req)
 if not errors:errors+=citation_errors(obj,manifest,passages)
 if not errors and role=='CURRENT_STATE':
  obs=obj.get('payload',{}).get('observations',[]);ids=[o['observation_id'] for o in obs]
  if len(ids)!=len(set(ids)):errors.append('Duplicate observation IDs')
  if len(ids)>req['payload']['max_observations']:errors.append('Observation limit exceeded')
 elif not errors:
  a=json.loads((work/'agent-a.json').read_text(encoding='utf-8-sig'));expectedids={x['observation_id'] for x in a['payload']['observations']};reviews=obj.get('payload',{}).get('upstream_review',[])
  seen={x.get('observation_id') for x in reviews}
  if expectedids!=seen or len(reviews)!=len(seen):errors.append('B must review every A observation exactly once')
  if obj.get('payload',{}).get('human_reviews'):errors.append('No attributed human reviews supplied; must be empty')
 rid=one(db,'select id from analysis.runs where run_key=%s',(req['run_id'],))['id'];valid=not errors
 oid=one(db,"""insert into analysis.agent_outputs(run_id,agent_role,output_json,schema_validated,validation_status,validation_details,contract_schema_sha256,prompt_sha256,model_details)
 values(%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s::jsonb) returning id""",(rid,role,j(obj if isinstance(obj,dict) else {'invalid_raw_output':obj}),valid,'VALID' if valid else 'INVALID',j({'errors':errors,'level':'schema + provenance checks; human semantic verification still required'}),sha((BASE/'contracts/contracts-v2.schema.json').read_bytes()),sha((work/('prompt-a.txt' if role=='CURRENT_STATE' else 'prompt-b.txt')).read_bytes()),j({'engine':'Codex CLI','instruction_release':'2.1.0+local-0.12'})))['id']
 result={'valid':valid,'errors':errors,'output_id':oid,'run_id':rid};(work/('validation-a.json' if role=='CURRENT_STATE' else 'validation-b.json')).write_text(j(result),encoding='utf-8')
 if not valid:
  stage(db,rid,'AGENT_A' if role=='CURRENT_STATE' else 'AGENT_B','FAILED',result);q(db,"update analysis.runs set status='FAILED',completed_at=now() where id=%s",(rid,));return result
 obs=obj['payload'].get('observations',[]);records=[]
 if role=='CURRENT_STATE':records=[(o['observation_id'],'OBSERVATION',o['statement'],o.get('level'),o) for o in obs]
 else:records=[(x['article_id'],'ARTICLE_ASSESSMENT',j({'title':x['title'],'currency':x['currency'],'quality':x['quality'],'why_relevant':x['why_relevant']})[:3000],None,x) for x in obj['payload'].get('articles',[])]+[('recommendation','FINDING',j({'recommendation':obj['payload']['recommendation'],'writing_backlog':obj['payload']['writing_backlog'],'limitations':obj['payload']['limitations']})[:3000],None,obj['payload'])]
 profile=model_profile(db,cfg)
 progress(f"{role}: saving {len(records)} records; local embedding model {cfg['EmbeddingModel']}, profile {profile['id']}")
 for key,kind,text,level,details in records:
  rec=one(db,"insert into analysis.records(run_id,agent_output_id,record_key,record_type,topic,statement,evidence_level,details) values(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) returning id",(rid,oid,role+':'+key,kind,req['topic'],text,level,j(details)))['id']
  # Store links only for literal excerpt matches from actual supplied units.
  cites=details.get('citations',details.get('existence_citations',[]))
  for cite in cites:
   for p in manifest['transcript']+passages:
    if cite['file']==p['locator']['file'] and cite['excerpt_or_observation'] in p['content_text']:
     q(db,"insert into analysis.record_evidence(record_id,content_unit_id,relationship,locator,excerpt) values(%s,%s,'SUPPORTS',%s::jsonb,%s) on conflict do nothing",(rec,p['id'],j(p['locator']),cite['excerpt_or_observation']))
  db.commit()
  progress(f"{role}: embedding record {key} with the shared local profile")
  v=embed(cfg,text)
  q(db,"insert into retrieval.analysis_embeddings(record_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s)",(rec,profile['id'],sha(text),vector(v),text));db.commit()
 stage(db,rid,'AGENT_A' if role=='CURRENT_STATE' else 'AGENT_B','PARTIAL' if obj['status']!='OK' else 'COMPLETE',result)
 stage(db,rid,'A_EMBED' if role=='CURRENT_STATE' else 'B_EMBED','COMPLETE',{'records':len(records)})
 if role=='ARTICLE_REVIEW':
  a=json.loads((work/'agent-a.json').read_text(encoding='utf-8-sig'));st='COMPLETE' if obj['status']=='OK' and a['status']=='OK' else 'PARTIAL'
  q(db,'update analysis.runs set status=%s,completed_at=now() where id=%s',(st,rid));stage(db,rid,'RETRIEVAL_READY',st,{'human_review':'not yet performed'})
 return result

def main(req):
 cfg=json.loads((BASE/'config/appsettings.json').read_text(encoding='utf-8-sig'));op=req['op'];args=req.get('args',{})
 if op=='scan':
  result=scan(cfg)
  try:
   with connect() as db:
    for f in result['files']:
     r=one(db,"select v.id,exists(select 1 from knowledge.extractions e where e.source_version_id=v.id and e.is_active and e.processor_version=%s) extracted from knowledge.source_versions v where v.storage_uri=%s and v.content_sha256=%s and v.lifecycle_status='ACTIVE'",(EXTRACTION_VERSION,Path(f['path']).absolute().as_uri(),f['sha256']))
     f['state']='UNCHANGED' if r and r['extracted'] else 'NEW_OR_PENDING'
  except Exception:result['database_comparison']='Unavailable; scan still read-only, database health must pass before processing'
  (BASE/'runtime').mkdir(exist_ok=True);(BASE/'runtime/last-scan.json').write_text(j(result),encoding='utf-8');return result
 if op=='process':return process(cfg,args)
 if op=='warm':return {'dimensions':len(embed(cfg,'TD startup model readiness check')),'model':cfg['EmbeddingModel']}
 if op=='validate':return {'errors':validate_contract(args['object'])}
 with connect() as db:
  if op.startswith('module_'):
   import module_review
   require_db(db)
   return module_review.main(db,cfg,op,args)
  if op=='migrate':migration(db);return {'migration':'010-local-files applied','database':'knowledge_poc'}
  if op=='status':return status(db)
  if op=='search':return search(db,cfg,args['query'],args.get('role'),args.get('limit',20))
  if op=='prepare_test':return prepare_test(db,cfg,args)
  if op=='save_output':return save_output(db,cfg,args)
  if op=='fail_run':
   q(db,"update analysis.runs set status='FAILED',completed_at=now() where run_key=%s",(args['run_key'],));return {'status':'FAILED'}
  if op=='prepare_b':
   work=Path(args['work']);a=json.loads((work/'agent-a.json').read_text(encoding='utf-8-sig'));req=a['payload']['request'];terms=' '.join(req['search_aliases'])+' '+req['question']
   data=search(db,cfg,terms,'EXISTING_ASSET',60);data['upstream']=a;data['search_terms']=terms;data['inventory_scope']='Top 60 hybrid candidates only. No company-wide absence conclusion permitted.'
   rid=one(db,'select id from analysis.runs where run_key=%s',(a['run_id'],))['id']
   for p in data['passages']:
    q(db,"insert into analysis.run_sources(run_id,source_version_id,coverage_status,search_terms,coverage_details) values(%s,%s,'SEARCHED',%s::jsonb,%s::jsonb) on conflict(run_id,source_version_id) do nothing",(rid,p['version_id'],j([terms]),j({'bounded_candidate_packet':True})))
   (work/'evidence-b.json').write_text(j(data),encoding='utf-8');return data
  raise ValueError('Unknown operation')
if __name__=='__main__':
 try:
  r=main(json.load(sys.stdin));print(j({'ok':True,'result':r}))
 except Exception as e:
  print(j({'ok':False,'error':str(e)}));sys.exit(1)
