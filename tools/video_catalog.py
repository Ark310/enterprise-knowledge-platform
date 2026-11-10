"""Readiness and exact source selection for registered local recordings. No video bytes in SQL."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import worker as w
from knowledge_scope import companion

def catalog(db,cfg):
 profile=w.model_profile(db,cfg)
 videos=w.q(db,"select v.id,v.storage_uri,v.content_sha256,v.evidence_role,v.source_modified_at,s.title from knowledge.source_versions v join knowledge.sources s on s.id=v.source_id where v.lifecycle_status='ACTIVE' and lower(v.storage_uri) ~ '[.](mp4|wmv|mov|mkv|avi|webm)$' order by v.storage_uri").fetchall()
 # Readiness matches retrieval's profile-specific extraction switch, not lifetime job totals.
 from retrieval_v017 import base_sql
 units=w.q(db,f"select version_id,count(*) units,count(e.content_unit_id) embedded from ({base_sql(cfg.get('SearchMode','improved_hnsw'),profile)}) b left join retrieval.content_embeddings e on e.content_unit_id=b.id and e.profile_id=%s group by version_id",(None,None,profile['id'])).fetchall()
 counts={str(x['version_id']):x for x in units}
 from workspace_ui import source_path
 root=Path(cfg['DataRoot']);rows=[];seen=set()
 def rel(uri):
  path=source_path(cfg,uri)
  return path.relative_to(root).as_posix() if path else None
 for video in videos:
  path=rel(video['storage_uri'])
  if not path:continue
  from knowledge_scope import resolve_bundle
  resolved=resolve_bundle(db,cfg,{'recording_names':[path]})
  matches=resolved['recordings'][0]['transcripts'] if resolved['recordings'] else []
  parts=[dict(file=rel(t['file']),units=int(counts.get(t['version_id'],{}).get('units',0)),embedded=int(counts.get(t['version_id'],{}).get('embedded',0))) for t in matches]
  ready=bool(parts) and all(t['units']>0 and t['embedded']==t['units'] for t in parts) and not resolved['blocking_errors']
  current=source_path(cfg,video['storage_uri'])
  modified=video.get('source_modified_at')
  fresh=bool(current and modified and abs(current.stat().st_mtime-modified.timestamp())<.01)
  if not fresh:ready=False
  rows.append({'version_id':str(video['id']),'file':path,'title':Path(path).stem,'role':video['evidence_role'],'state':'READY' if ready else 'NEEDS_PROCESSING' if matches else 'MISSING_TRANSCRIPT','transcripts':parts,'freshness':'Metadata matches imported revision; video hash checked on selection' if fresh else 'File changed or has not been scanned; scan and process first'});seen.add(path.casefold())
 manifest=w.BASE/'runtime/last-scan.json'
 if manifest.is_file():
  import json
  for f in json.loads(manifest.read_text(encoding='utf-8')).get('files',[]):
   path=f['relative']
   if Path(path).suffix.lower() in w.VIDEO_EXT and path.casefold() not in seen:rows.append({'version_id':None,'file':path,'title':Path(path).stem,'role':f['role'],'state':'NEEDS_PROCESSING','transcripts':[]})
 return {'videos':rows,'profile':str(profile['id']),'note':'Registered source revisions and current-profile text vectors. Scan, then Process new files after copying recordings and matching SRTs.'}

def pins(db,cfg,paths):
 if not isinstance(paths,list) or len(paths)>2 or any(not isinstance(x,str) for x in paths):raise ValueError('Select up to two videos')
 from workspace_ui import source_path
 selected=[]
 for value in paths:
  path=source_path(cfg,value)
  if not path or path.suffix.lower() not in w.VIDEO_EXT:raise ValueError('Selected recording is missing or outside the data folder')
  row=w.one(db,"select id,content_sha256 from knowledge.source_versions where storage_uri=%s and lifecycle_status='ACTIVE'",(path.absolute().as_uri(),))
  if not row or row['content_sha256']!=w.file_hash(path):raise ValueError('Selected video is new or changed. Run Scan, then Process new files first.')
  from knowledge_scope import resolve_bundle
  bundle=resolve_bundle(db,cfg,{'recording_names':[value]})
  if bundle['blocking_errors']:raise ValueError('; '.join(bundle['blocking_errors']))
  rel=path.relative_to(Path(cfg['DataRoot'])).as_posix()
  if rel not in selected:selected.append(rel)
 return {'recordings':selected}
