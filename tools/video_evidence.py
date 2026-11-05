"""Reusable selected frames; media remains on disk, exact locators/hashes live in PostgreSQL."""
import json,re,subprocess,math,hashlib
from pathlib import Path
import worker as w

def cache_key(source_hash,extractor,start,end,cap):return w.sha(w.j([source_hash,extractor,float(start),float(end),int(cap),'2sec-1280-v1']))
def valid_cache(rows):
    if not isinstance(rows,list) or not rows:return False
    try:
        return all(isinstance(r,dict) and isinstance(r.get('path'),str) and isinstance(r.get('sha256'),str) and isinstance(r.get('seconds'),(int,float)) and Path(r['path']).is_file() and w.file_hash(r['path'])==r['sha256'] for r in rows)
    except OSError:return False

def decoded_times(stderr,count):
    times=[float(t) for t in re.findall(r'Parsed_showinfo[^\n]*pts_time:([0-9.]+)',stderr)]
    # FFmpeg may log a lookahead frame after -t / -frames:v has limited output.
    if count<1 or len(times)<count:raise ValueError('Cannot map every decoded frame to its actual timestamp')
    return times[:count]

def frames(db,cfg,rec,start,end,cap=60,verified_source_hash=None):
    import module_review
    rec=Path(rec);source_hash=verified_source_hash or w.file_hash(rec)
    ffmpeg=cfg.get('FFmpegExecutable') or __import__('shutil').which('ffmpeg')
    if not ffmpeg:raise ValueError('ffmpeg not available; no visual evidence can be claimed')
    version=subprocess.run([ffmpeg,'-version'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
    if version.returncode:raise ValueError('ffmpeg version check failed')
    extractor=w.sha(version.stdout+version.stderr+'2sec-1280-v1')
    folder=w.BASE/'runtime/frame-cache'/cache_key(source_hash,extractor,start,end,cap);folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'frames.json';rows=[];reused=False
    if manifest.is_file():
        try:rows=json.loads(manifest.read_text(encoding='utf-8'));reused=valid_cache(rows)
        except (ValueError,OSError):pass
    if not reused:
        # Remove only this extractor/range's stale frames; retain unrelated cached evidence.
        for p in folder.glob('frame-*.jpg'):p.unlink()
        result=module_review.decode_frames(ffmpeg,rec,folder,{'start':start,'end':end},folder/'frame-%04d.jpg',max_frames=cap)
        paths=sorted(folder.glob('frame-*.jpg'));times=decoded_times(result.stderr,len(paths))
        rows=[{'path':str(p),'seconds':float(start)+times[i],'source_id':f'{float(start)+times[i]:.3f}','sha256':w.file_hash(p)} for i,p in enumerate(paths)]
        if any(r['seconds']<float(start)-.01 or r['seconds']>float(end)+.1 for r in rows):raise ValueError('Decoded frame outside requested range')
        manifest.write_text(w.j(rows),encoding='utf-8')
    if verified_source_hash is None and w.file_hash(rec)!=source_hash:raise ValueError('Recording changed during frame preparation')
    sv=w.one(db,"select id from knowledge.source_versions where storage_uri=%s and content_sha256=%s and lifecycle_status='ACTIVE'",(rec.absolute().as_uri(),source_hash))
    if not sv:raise ValueError('Import this exact recording revision before extracting frames')
    out=[]
    for row in rows:
        frame=w.one(db,"insert into knowledge.poc_video_frames(source_version_id,extractor_key,frame_seconds,storage_uri,image_sha256,metadata) values(%s,%s,%s,%s,%s,%s::jsonb) on conflict(source_version_id,extractor_key,frame_seconds,image_sha256) do update set storage_uri=excluded.storage_uri returning id",(sv['id'],extractor,row['seconds'],Path(row['path']).absolute().as_uri(),row['sha256'],w.j({'sampling':'2-second selected frames; between-frame actions unverified','range_start':start,'range_end':end,'cap':cap})))
        out.append(dict(row,frame_id=str(frame['id']),cache_reused=reused,recording_file=rec.relative_to(Path(cfg['DataRoot'])).as_posix()))
    return out

def link(db,record_id,citation,frames_):
    key=citation.get('source_id');matches=[f for f in frames_ if f.get('source_id')==key]
    for f in matches:
        if f.get('frame_id'):w.q(db,'insert into analysis.poc_frame_evidence(record_id,frame_id) values(%s,%s) on conflict do nothing',(record_id,f['frame_id']))
