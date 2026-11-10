"""Local web workspace: durable chat audit and scoped media, never an embedding corpus."""
import base64,hashlib,html,io,json,mimetypes,os,re,uuid,warnings
from pathlib import Path
from urllib.parse import unquote,urlparse
import worker as w
MAX_BYTES=10*1024*1024

def safe_file(root,relative):
 root=Path(root).resolve();raw=Path(relative)
 if raw.is_absolute() or '..' in raw.parts:return None
 path=root/raw
 if any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):return None
 try:path=path.resolve();path.relative_to(root)
 except (ValueError,OSError):return None
 return path if path.is_file() else None

def image_info(path):
 from PIL import Image
 with warnings.catch_warnings():
  warnings.simplefilter('error',Image.DecompressionBombWarning)
  with Image.open(path) as im:
   if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>20000000:raise ValueError('Use PNG, JPEG or WebP up to 20 megapixels')
   im.verify()
  with Image.open(path) as im:return {'width':im.width,'height':im.height,'mime':Image.MIME[im.format]}

def normalize_upload(data,destination):
 from PIL import Image,ImageOps
 if not 0<len(data)<=MAX_BYTES:raise ValueError('Image limit is 10 MB')
 try:
  info=image_info(io.BytesIO(data))
  with Image.open(io.BytesIO(data)) as im:
   im=ImageOps.exif_transpose(im);im.thumbnail((2560,2560));im.convert('RGB').save(destination,'PNG')
  return dict(image_info(destination),sha256=w.file_hash(destination))
 except Exception as e:
  Path(destination).unlink(missing_ok=True);raise ValueError('Image could not be decoded safely; use PNG, JPEG or WebP') from e

def linked_images(root,article):
 try:text=Path(article).read_text(encoding='utf-8-sig')[:2000000]
 except (UnicodeError,OSError):return []
 found=[]
 links=re.findall(r'!\[([^\]]*)\]\(([^)]+)\)',text)+[('Article image',u) for u in re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\']',text,re.I)]
 if not links and (Path(article).parent/'screenshot.png').is_file():links=[('Article screenshot','screenshot.png')]
 for label,url in links:
  url=url.strip().split(' "',1)[0].strip('<>')
  if urlparse(url).scheme or url.startswith(('/','\\')):continue
  rel=Path(article).parent/ unquote(url)
  try:rel=rel.resolve().relative_to(Path(root).resolve())
  except ValueError:continue
  p=safe_file(root,rel)
  if p and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
   try:image_info(p);found.append({'path':str(p),'label':label or p.name})
   except Exception:pass
 return found[:6]

def private_root(cfg):
 path=cfg.get('WebDataRoot') or str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'Contoso'/'Workspace')
 return Path(path).expanduser().resolve()

def asset(db,chat,kind,path,label,metadata=None,expected_sha256=None):
 path=Path(path);digest=w.file_hash(path)
 if expected_sha256 and digest!=expected_sha256:raise ValueError('Cited source revision has changed')
 ident=str(uuid.uuid4());mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
 w.q(db,'insert into workspace_ui.assets(id,chat_id,kind,label,path,sha256,mime,metadata) values(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(ident,chat,kind,label[:400],str(path),digest,mime,w.j(metadata or {})))
 return {'id':ident,'kind':kind,'label':label[:400],'mime':mime,'metadata':metadata or {}}

def chat_row(db,chat):
 c=w.one(db,'select * from workspace_ui.chats where id=%s',(str(uuid.UUID(chat)),))
 if not c:raise ValueError('Chat not found')
 return c

def authorized_path(cfg,row):
 path=Path(row['path'])
 root=private_root(cfg) if row['kind']=='USER_UPLOAD' else Path(cfg['DataRoot'])
 if row['kind']=='FRAME':root=w.BASE/'runtime'
 try:relative=path.relative_to(root)
 except ValueError:raise ValueError('Asset outside permitted source root')
 found=safe_file(root,relative)
 if not found or w.file_hash(found)!=row['sha256']:raise ValueError('Source is missing or has changed since this answer')
 return found

def source_path(cfg,uri):
 parsed=urlparse(uri)
 raw=unquote(parsed.path) if parsed.scheme=='file' else uri
 if re.match(r'^/[A-Za-z]:/',raw):raw=raw[1:]
 path=Path(raw);root=Path(cfg['DataRoot'])
 try:rel=path.relative_to(root) if path.is_absolute() else path
 except ValueError:return None
 return safe_file(root,rel)

def register_source(db,cfg,chat,p):
 path=source_path(cfg,p.get('file') or p.get('storage_uri') or '')
 if not path:return None
 version=p.get('version_id') or p.get('source_version_id')
 if not version and p.get('unit_id'):
  row=w.one(db,'select e.source_version_id from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id where u.id=%s',(p['unit_id'],));version=str(row['source_version_id']) if row else None
 if not version:return None
 pinned=w.one(db,'select content_sha256,storage_uri from knowledge.source_versions where id=%s',(version,))
 if not pinned or source_path(cfg,pinned['storage_uri'])!=path:return None
 try:return asset(db,chat,'SOURCE',path,p.get('source_title') or (path.parent.name if path.name in ('article.md','article.json') else path.name),{'locator':p.get('locator',{}),'original_url':p.get('source_metadata',{}).get('url'),'evidence_id':p.get('evidence_id'),'file':p.get('file') or pinned['storage_uri'],'source_version_id':str(version)},pinned['content_sha256'])
 except (ValueError,OSError):return None

def recover(db,chat):
 # A crash never silently replays a model request. Only completed messages count as completed jobs.
 pending=w.q(db,"""select m.payload->>'job' job from workspace_ui.messages m
 where m.chat_id=%s and m.role='user' and m.payload ? 'job'
 and not exists(select 1 from workspace_ui.messages x where x.chat_id=m.chat_id and x.role in('assistant','system') and x.payload->>'job'=m.payload->>'job')
 and not exists(select 1 from workspace_ui.engine_lock l where l.owner::text=m.payload->>'job' and l.expires_at>now())""",(chat,)).fetchall()
 for p in pending:
  ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'workspace-interrupted:'+p['job']))
  w.q(db,"insert into workspace_ui.messages(id,chat_id,role,body,payload) values(%s,%s,'system',%s,%s::jsonb) on conflict(id) do nothing",(ident,chat,'This request was interrupted before a completed reply was saved. It was not restarted automatically. You can send it again.',w.j({'job':p['job'],'status':'INTERRUPTED'})))
 if pending:db.commit()

def main(db,cfg,op,args):
 if op in ('ui_videos','ui_video_pins'):
  import video_catalog
  return video_catalog.catalog(db,cfg) if op=='ui_videos' else video_catalog.pins(db,cfg,args.get('recordings',[]))
 if op=='ui_video_source':
  chat_row(db,args['chat_id'])
  path=source_path(cfg,args['file'])
  if not path or path.suffix.lower() not in w.VIDEO_EXT:raise ValueError('Choose a registered recording under the data folder')
  version=w.one(db,"select id from knowledge.source_versions where storage_uri=%s and lifecycle_status='ACTIVE'",(path.absolute().as_uri(),))
  if not version:raise ValueError('Process this recording first')
  result=register_source(db,cfg,args['chat_id'],{'file':args['file'],'version_id':str(version['id'])})
  if not result:raise ValueError('Recording changed or unavailable')
  db.commit();return result
 if op=='ui_list':return {'chats':w.q(db,'select id,poc,title,created_at,updated_at from workspace_ui.chats where poc=%s order by updated_at desc limit 500',(int(args['poc']),)).fetchall()}
 if op=='ui_create':
  chat=str(uuid.uuid4());poc=int(args['poc'])
  w.q(db,'insert into workspace_ui.chats(id,poc,title) values(%s,%s,%s)',(chat,poc,'New chat'));db.commit();return chat_row(db,chat)
 chat=args.get('chat_id')
 if op in ('ui_get','ui_message','ui_state','ui_upload','ui_asset','ui_assets','ui_sources','ui_present','ui_candidates'):chat_row(db,chat)
 if op=='ui_get':
  recover(db,chat)
  c=chat_row(db,chat);before=int(args.get('before',9223372036854775807))
  messages=w.q(db,'select id,seq,role,body,payload,created_at from workspace_ui.messages where chat_id=%s and seq<%s order by seq desc limit 101',(chat,before)).fetchall()
  c['has_older']=len(messages)>100;c['messages']=list(reversed(messages[:100]));c['assets']=w.q(db,"select id,kind,label,mime,metadata from workspace_ui.assets where chat_id=%s and kind='USER_UPLOAD' order by created_at desc limit 4",(chat,)).fetchall();return c
 if op=='ui_message':
  ident=str(uuid.UUID(args['id']));body=str(args['body']);role=args['role']
  if len(body)>200000:raise ValueError('Message too long')
  w.q(db,'insert into workspace_ui.messages(id,chat_id,role,body,payload) values(%s,%s,%s,%s,%s::jsonb) on conflict(id) do nothing',(ident,chat,role,body,w.j(args.get('payload',{}))))
  if role=='user':w.q(db,"update workspace_ui.chats set title=case when title='New chat' then %s else title end,updated_at=now() where id=%s",(body[:70],chat))
  db.commit();return {'saved':True}
 if op=='ui_state':w.q(db,'update workspace_ui.chats set context=%s::jsonb,updated_at=now() where id=%s',(w.j(args['context']),chat));db.commit();return {'saved':True}
 if op=='ui_upload':
  data=base64.b64decode(args['base64'],validate=True);root=private_root(cfg)/'uploads'/str(uuid.UUID(chat));root.mkdir(parents=True,exist_ok=True);path=root/(str(uuid.uuid4())+'.png')
  info=normalize_upload(data,path)
  try:r=asset(db,chat,'USER_UPLOAD',path,str(args.get('name','Pasted image')),info);db.commit();return r
  except Exception:path.unlink(missing_ok=True);raise
 if op=='ui_assets':
  ids=[str(uuid.UUID(x)) for x in args.get('ids',[])]
  if len(ids)>4:raise ValueError('Attach up to four images')
  rows=w.q(db,"select * from workspace_ui.assets where chat_id=%s and kind='USER_UPLOAD' and id=any(%s::uuid[])",(chat,ids)).fetchall()
  if len(rows)!=len(set(ids)):raise ValueError('Attachment does not belong to this chat')
  return {'images':[dict(r,path=str(authorized_path(cfg,r))) for r in rows]}
 if op=='ui_asset':
  r=w.one(db,'select * from workspace_ui.assets where chat_id=%s and id=%s',(chat,str(uuid.UUID(args['id']))))
  if not r:raise ValueError('Asset not found')
  path=authorized_path(cfg,r);r['path']=str(path)
  if args.get('text'):
   r['text']=path.read_text(encoding='utf-8-sig',errors='replace')[:2000000] if path.suffix.lower() in ('.md','.txt','.json','.srt','.vtt','.csv') else None
  return r
 if op=='ui_candidates':
  rows=[]
  for p in args.get('evidence',[])[:100]:
   if p.get('kind')!='SOURCE':continue
   path=source_path(cfg,p.get('file',''))
   if not path:continue
   for im in linked_images(Path(cfg['DataRoot']),path):
    if im['path'] in {x['path'] for x in rows}:continue
    rows.append(dict(im,source_file=p.get('file'),source_version_id=p.get('version_id'),image_sha256=w.file_hash(im['path'])))
    if len(rows)>=4:return {'images':rows}
  return {'images':rows}
 if op=='ui_present':
  sources=[];images=[];seen=set();unavailable=[];source_assets={}
  for p in args.get('evidence',[]):
   if p.get('kind') in ('SOURCE','FRAME','SOURCE_IMAGE'):
    if p.get('kind')=='SOURCE_IMAGE':p=dict(p,file=p.get('source_file',p.get('file')))
    key=p.get('file')
    if key not in seen:
     seen.add(key);s=register_source(db,cfg,chat,p)
     if s:sources.append(s);source_assets[key]=s['id']
     else:unavailable.append(key or 'Cited source')
   if p.get('kind') in ('FRAME','SOURCE_IMAGE'):
    path=Path(p['path']);root=w.BASE/'runtime' if p['kind']=='FRAME' else Path(cfg['DataRoot'])
    try:rel=path.relative_to(root)
    except ValueError:continue
    path=safe_file(root,rel)
    if path and w.file_hash(path)==p['image_sha256']:
     images.append(asset(db,chat,'FRAME' if p['kind']=='FRAME' else 'SOURCE_IMAGE',path,p.get('label') or p.get('file','Video frame'),{'evidence_id':p['evidence_id'],'locator':p.get('locator',{}),'file':p.get('file'),'source_file':p.get('source_file'),'recording_asset_id':source_assets.get(p.get('file')) if p['kind']=='FRAME' else None}))
  db.commit();return {'sources':sources,'images':images,'unavailable':unavailable}
 if op=='ui_answer':
  chat_row(db,args['chat_id'])
  turn=w.one(db,"select * from knowledge_qa.turns where id=%s and session_id=%s and status='VERIFIED'",(str(uuid.UUID(args['turn_id'])),str(uuid.UUID(args['chat_id']))))
  if not turn:raise ValueError('No verified answer for this chat')
  ids=list(dict.fromkeys([c['evidence_id'] for claim in turn['answer']['claims'] for c in claim['citations']]+turn['answer'].get('illustrations',[])))
  rows=w.q(db,'select evidence_key,snapshot from knowledge_qa.evidence where turn_id=%s',(turn['id'],)).fetchall();by={p['evidence_key']:p['snapshot'] for p in rows}
  return {'answer':turn['answer'],'evidence':[by[x] for x in ids if x in by]}
 if op=='ui_review_context':
  chat_row(db,chat)
  import module_review
  report=module_review.results(db,args['run_key']);run=report['run_id']
  rows=w.q(db,"""select distinct f.id,f.storage_uri,f.image_sha256,f.frame_seconds,v.storage_uri recording_uri
  from analysis.records r join analysis.poc_frame_evidence e on e.record_id=r.id
  join knowledge.poc_video_frames f on f.id=e.frame_id join knowledge.source_versions v on v.id=f.source_version_id
  where r.run_id=%s order by f.frame_seconds limit 4""",(run,)).fetchall()
  images=[]
  for row in rows:
   path=Path(unquote(urlparse(row['storage_uri']).path))
   if re.match(r'^/[A-Za-z]:/',str(path)):path=Path(str(path)[1:])
   try:rel=path.relative_to(w.BASE/'runtime')
   except ValueError:continue
   found=safe_file(w.BASE/'runtime',rel)
   if not found or w.file_hash(found)!=row['image_sha256']:continue
   a=asset(db,chat,'FRAME',found,'Recording at '+str(row['frame_seconds'])+' seconds',{'frame_id':str(row['id']),'locator':{'start_seconds':str(row['frame_seconds'])},'recording_uri':row['recording_uri']})
   images.append(dict(a,path=str(found)))
  db.commit();return {'images':images}
 if op=='ui_review_sources':
  chat_row(db,args['chat_id']);sources=[];seen=set();unavailable=[]
  # Resolve the saved report afresh, never trust client-supplied paths as an authorization.
  import module_review
  report=module_review.results(db,args['report']['run_key'])
  selected=args.get('unit_ids')
  for v in w.q(db,"select v.id,v.storage_uri from analysis.run_sources r join knowledge.source_versions v on v.id=r.source_version_id where r.run_id=%s and v.evidence_role='CURRENT_STATE'",(report['run_id'],)).fetchall():
   entry=register_source(db,cfg,chat,{'storage_uri':v['storage_uri'],'version_id':str(v['id'])})
   if entry:sources.append(entry)
   else:unavailable.append(v['storage_uri'])
  for row in report.get('rows',[]):
   for c in row.get('article_citations',[]):
    if selected is not None and c.get('unit_id') not in selected:continue
    file=(c.get('locator') or {}).get('file')
    if not file or file in seen:continue
    seen.add(file);p={'unit_id':c.get('unit_id'),'file':file,'source_title':c.get('article_title'),'locator':c.get('locator'),'source_metadata':{'url':c.get('source_url')}}
    entry=register_source(db,cfg,args['chat_id'],p)
    if entry:sources.append(entry)
    else:unavailable.append(file)
  images=[]
  for ident in args.get('image_ids',[]):
   row=w.one(db,"select * from workspace_ui.assets where id=%s and chat_id=%s and kind='FRAME'",(str(uuid.UUID(ident)),chat))
   if not row:raise ValueError('Review image not in this chat')
   frame=w.one(db,"select 1 from analysis.poc_frame_evidence e join analysis.records r on r.id=e.record_id where e.frame_id=%s and r.run_id=%s",(row['metadata']['frame_id'],report['run_id']))
   if not frame:raise ValueError('Image outside selected review')
   authorized_path(cfg,row)
   images.append({k:row[k] for k in ('id','kind','label','mime','metadata')})
  db.commit();return {'sources':sources,'images':images,'unavailable':unavailable}
 if op=='ui_claim':
  owner=str(uuid.UUID(args['owner']));r=w.one(db,"insert into workspace_ui.engine_lock(id,owner,expires_at) values(1,%s,now()+interval '90 seconds') on conflict(id) do update set owner=excluded.owner,expires_at=excluded.expires_at where workspace_ui.engine_lock.expires_at<now() or workspace_ui.engine_lock.owner=excluded.owner returning owner",(owner,));db.commit()
  if not r:raise ValueError('Another Workspace job is running')
  return {'claimed':True}
 if op=='ui_renew':
  r=w.one(db,"update workspace_ui.engine_lock set expires_at=now()+interval '90 seconds' where id=1 and owner=%s returning owner",(str(uuid.UUID(args['owner'])),));db.commit()
  if not r:raise ValueError('Workspace engine lease lost')
  return {'renewed':True}
 if op=='ui_release':w.q(db,'delete from workspace_ui.engine_lock where id=1 and owner=%s',(str(uuid.UUID(args['owner'])),));db.commit();return {'released':True}
 raise ValueError('Unknown workspace operation')
