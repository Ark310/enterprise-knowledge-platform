"""POC 2 only: bounded, pinned recording samples. Never treats speech as visual proof."""
import re,urllib.parse,shutil
from pathlib import Path
import worker as w

def recording_key(name):
 name=Path(name.replace('\\','/')).name
 name=re.sub(r'\.(mp4|mkv|mov|wmv|avi|webm)$','',name,flags=re.I)
 return ' '.join(re.findall(r'[a-z0-9]+',name.casefold()))

def human_key(name):
 return recording_key(re.sub(r'\s*\[[A-Za-z0-9_-]{6,}\](?=\.[^.]+$|$)','',name))

def recording_matches(videos,name,root):
 name=name.replace('\\','/')
 if '/' not in name:
  exact=[v for v in videos if recording_key(urllib.parse.unquote(urllib.parse.urlparse(v['storage_uri']).path))==recording_key(name)]
  return exact or [v for v in videos if human_key(urllib.parse.unquote(urllib.parse.urlparse(v['storage_uri']).path))==human_key(name)]
 def pathkey(value):return urllib.parse.unquote(value).replace('\\','/').strip('/').casefold()
 if name.startswith('file:'):wanted=pathkey(urllib.parse.urlparse(name).path)
 elif name.startswith('/') or re.match(r'^[A-Za-z]:/',name):wanted=pathkey(name)
 else:wanted=pathkey(str(root)+'/'+name)
 return [v for v in videos if pathkey(urllib.parse.urlparse(v['storage_uri']).path)==wanted]

def sample_times(duration,passages,terms,cap=12):
 # Always inspect opening and ending as well as question-bearing transcript locations.
 end=max(0,duration-.2);out=[]
 def add(t):
  t=round(max(0,min(float(t),end)),3)
  if t not in out and len(out)<cap:out.append(t)
 boundary_slots=min(2,max(0,cap//3))
 topic_cap=cap-boundary_slots
 ranked=sorted((p for p in passages if p.get('start_seconds') is not None),key=lambda p:-sum(t.casefold() in p['content_text'].casefold() for t in terms))
 for p in ranked:
  if not any(t.casefold() in p['content_text'].casefold() for t in terms):continue
  if len(out)<topic_cap:add(p['start_seconds'])
  if len(out)<topic_cap:add(float(p['start_seconds'])+2)
 for t in [0,end,max(0,duration-4),max(0,duration-12)]:add(t)
 for fraction in [.08,.25,.5,.75]:add(duration*fraction)
 return sorted(out)

def prepare(db,cfg,normalized,passages):
 names=normalized.get('recording_names',[])[:2]
 report={'requested':bool(normalized.get('visual_check',False)),'recordings':[],'limitations':['Selected still frames only; actions between frames, audio alignment and successful persistence remain unverified unless evidence establishes them.']}
 if not report['requested']:return [],report
 if not names:
  report['limitations'].append('No exact recording title identified. Ask for the recording title or relative path.');return [],report
 videos=w.q(db,"select id,storage_uri,content_sha256 from knowledge.source_versions where lifecycle_status='ACTIVE' and lower(storage_uri) ~ '[.](mp4|mkv|mov|wmv|avi|webm)$'").fetchall()
 out=[]
 import module_review,video_evidence
 for name in names:
  matches=recording_matches(videos,name,Path(cfg['DataRoot']))
  entry={'requested_name':name,'matching_recordings':len(matches),'status':'UNAVAILABLE'};report['recordings'].append(entry)
  if len(matches)!=1:
   entry['reason']='Exact recording title missing or ambiguous; no substitute inspected.';continue
  sv=matches[0]
  try:
   parsed=urllib.parse.urlparse(sv['storage_uri'])
   if parsed.scheme!='file' or parsed.netloc:raise ValueError('Only local registered recordings are supported')
   path=urllib.parse.unquote(parsed.path)
   if re.match(r'^/[A-Za-z]:/',path):path=path[1:]
   root=Path(cfg['DataRoot']).resolve();rec=w.safe_path(root,Path(path));rel=rec.relative_to(root).as_posix()
   if w.file_hash(rec)!=sv['content_sha256']:raise ValueError('Recording changed since import; run /process first')
   duration,_=module_review.duration(cfg,rec)
   # Associate only the transcript for THIS recording, not a similarly named video.
   stem=rec.with_suffix('').as_uri().casefold()
   relevant=[p for p in passages if p.get('storage_uri','').casefold() in {stem+'.srt',stem+'.vtt'}]
   samples=sample_times(duration,relevant,normalized.get('keywords',[]))
   entry.update(status='SAMPLED',file=rel,source_version_id=str(sv['id']),duration_seconds=duration,sample_times=samples)
   for seconds in samples:
    for frame in video_evidence.frames(db,cfg,rec,seconds,min(duration,seconds+.18),cap=1,verified_source_hash=sv['content_sha256']):
     text=f'Sampled video frame at {frame["seconds"]:.3f} seconds from {rel}. Image attached; this descriptor alone does not establish screen content or a successful outcome.'
     out.append({'kind':'FRAME','frame_id':frame['frame_id'],'version_id':str(sv['id']),'file':rel,'text':text,'path':frame['path'],'image_sha256':frame['sha256'],'recording_sha256':sv['content_sha256'],'recording_uri':sv['storage_uri'],'locator':{'file':rel,'start_seconds':frame['seconds'],'end_seconds':frame['seconds']},'evidence_role':'SAMPLED_VISUAL'})
   if w.file_hash(rec)!=sv['content_sha256']:raise ValueError('Recording changed during sample preparation')
  except (ValueError,OSError,RuntimeError,TimeoutError,__import__('subprocess').SubprocessError) as e:
   entry.update(status='UNAVAILABLE',reason=str(e)[:1000])
   # Don't publish a partially sampled recording as a successful inspection.
   out=[p for p in out if p['version_id']!=str(sv['id'])]
 return out,report

def stage_images(evidence,folder):
 """Run-local hash-checked copies make exports reproducible; DB keeps lightweight locators."""
 folder=Path(folder)/'sampled-frames';folder.mkdir(parents=True,exist_ok=True)
 for p in evidence:
  if p['kind']!='FRAME':continue
  source=Path(p['path'])
  if not source.is_file() or w.file_hash(source)!=p['image_sha256']:raise ValueError('Sampled frame missing or changed')
  target=folder/(p['frame_id']+'.jpg')
  if not target.exists():shutil.copyfile(source,target)
  if w.file_hash(target)!=p['image_sha256']:raise ValueError('Run frame snapshot mismatch')
  p['path']=str(target)
 return evidence
